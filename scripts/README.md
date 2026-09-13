# 🔨 Scripts Module — Data Loading & Embedding

## Overview

This module contains three Python scripts that set up the project's data infrastructure:

| Script | Purpose | Target |
|---|---|---|
| `data_generator.py` | Generates synthetic e-commerce data warehouse | JSON files |
| `load_graph.py` | Loads data into Neo4j as a knowledge graph | Neo4j |
| `embed_metadata.py` | Embeds descriptions into a vector database | ChromaDB |

---

## Technologies Used

### Neo4j (Graph Database)
**What it is**: Neo4j is a **graph database** — unlike traditional relational databases (MySQL, PostgreSQL) that store data in tables with rows and columns, Neo4j stores data as **nodes** (entities) and **relationships** (connections between entities).

**Why it matters for lineage**: Data lineage is inherently a graph problem. "Table A is read by Job X which writes to Table B" is a natural graph structure:
```
(Table A) ←[:READS_FROM]← (Job X) —[:WRITES_TO]→ (Table B)
```

**Query language — Cypher**: Neo4j uses **Cypher**, a declarative query language designed for graphs:
```cypher
-- Find all tables that curated_orders depends on
MATCH (t:Table {name: 'curated_orders'})-[:DEPENDS_ON*1..]->(up:Table)
RETURN up.name
```

**How we use it**: `load_graph.py` creates nodes and relationships using the Python `neo4j` driver, which communicates with Neo4j over the Bolt protocol.

### ChromaDB (Vector Database)
**What it is**: Chroma is a **vector database** — it stores data as high-dimensional numerical vectors (called **embeddings**) and finds similar items by computing mathematical distance between vectors.

**How it works**:
1. Text → Embedding model → Vector (array of 384 numbers)
2. Store the vector with metadata in Chroma
3. To search: convert query to a vector, find the closest stored vectors

**Why it matters**: Enables **semantic search**. When a user asks "tables about customer refunds," we don't need an exact keyword match — we find tables whose descriptions are *semantically similar* to "customer refunds."

### sentence-transformers (Embedding Model)
**What it is**: A Python library that converts text into dense numerical vectors that capture semantic meaning. We use the `all-MiniLM-L6-v2` model.

**Key properties**:
- Runs locally on CPU (no GPU required, no API key)
- Produces 384-dimensional vectors
- Similar texts produce similar vectors (measured by cosine similarity)

**Example**:
```
"Payment refund processing" → [0.12, -0.45, 0.78, ..., 0.33]  (384 numbers)
"Customer refund handling"  → [0.11, -0.43, 0.76, ..., 0.31]  (very similar!)
"Shipping carrier tracking" → [-0.56, 0.22, -0.11, ..., 0.89] (very different)
```

---

## Script Details

### `data_generator.py` — Synthetic Data Generator

**Purpose**: Creates a reproducible synthetic dataset representing a "ShopStream" e-commerce data warehouse.

**What it generates**:
- 22 tables across 4 layers (raw → staging → curated → reporting)
- 170 columns with data types and natural-language descriptions
- 21 ETL jobs with read/write lineage
- 190 job run records (7 days, ~10% failure rate)

**How to run**:
```bash
python scripts/data_generator.py
```

**Output**: JSON files in `data/synthetic/`

**Design decisions**:
- Fixed random seed (`random.seed(42)`) for reproducibility
- Rich descriptions written for each table/column — these are critical for the vector search to work well
- Realistic job schedules (cron format) and failure patterns

---

### `load_graph.py` — Neo4j Graph Loader

**Purpose**: Reads the JSON data files and creates a complete lineage graph in Neo4j.

**Graph schema created**:

```
Node Types:
  • Table   (name, layer, description, column_count)
  • Column  (column_name, table_name, data_type, description)
  • Job     (name, description, schedule, owner)
  • JobRun  (run_id, status, started_at, duration_seconds, error_message, records_processed)

Relationships:
  • (Table)  -[:HAS_COLUMN]->  (Column)
  • (Job)    -[:READS_FROM]->  (Table)
  • (Job)    -[:WRITES_TO]->   (Table)
  • (Table)  -[:DEPENDS_ON]->  (Table)     ← automatically inferred!
  • (JobRun) -[:RUN_OF]->      (Job)
```

**Key feature — DEPENDS_ON inference**: If Job X reads from Table A and writes to Table B, the script automatically creates a `DEPENDS_ON` relationship: `(Table B)-[:DEPENDS_ON]->(Table A)`. This enables transitive lineage queries like "show me all upstream dependencies."

**How to run**:
```bash
# First time (clears existing data)
python scripts/load_graph.py --clear

# Subsequent loads (idempotent, uses MERGE)
python scripts/load_graph.py
```

**Idempotency**: Uses Cypher `MERGE` instead of `CREATE`, so running the script multiple times doesn't create duplicates.

**Verification**: After loading, the script runs verification queries and prints a summary:
```
--- Graph Verification Summary ---
Tables: 22
Columns: 170
Jobs: 21
Job Runs: 190
HAS_COLUMN rels: 170
READS_FROM rels: 24
WRITES_TO rels: 22
DEPENDS_ON rels: 19
RUN_OF rels: 190
----------------------------------
```

---

### `embed_metadata.py` — Chroma Vector Embedder

**Purpose**: Converts table and column descriptions into vector embeddings and stores them in ChromaDB for semantic search.

**How it works**:
1. Reads `tables.json` and `columns.json`
2. For each table, creates a rich text document:
   ```
   Table: curated_orders
   Layer: curated
   Description: Conformed order fact table — the single source of truth for order analytics...
   ```
3. Generates a 384-dimensional embedding using sentence-transformers
4. Stores in Chroma with metadata (type, table_name, layer, etc.)

**Document ID convention**: 
- Tables: `table_{table_name}` (e.g., `table_curated_orders`)
- Columns: `column_{table_name}_{column_name}` (e.g., `column_curated_orders_order_id`)

**How to run**:
```bash
python scripts/embed_metadata.py
```

**Idempotency**: Uses Chroma's `upsert` operation — safe to run multiple times.

**Test output**: After embedding, runs a sample similarity search for "payment refunds" and shows the top 3 results with distances.

**Importable function**: The `search_similar(query_text, n_results=5)` function can be imported by other modules for ad-hoc searches.

---

## Execution Order

These scripts must be run in order (each depends on the previous):

```
1. data_generator.py  →  Produces JSON files
2. load_graph.py      →  Reads JSON, writes to Neo4j (requires Neo4j running)
3. embed_metadata.py  →  Reads JSON, writes to Chroma
```

## Prerequisites

- **Neo4j**: Must be running before `load_graph.py` (use `docker-compose up -d`)
- **Python packages**: `neo4j`, `chromadb`, `sentence-transformers` (in `requirements.txt`)
- **No Ollama needed**: These scripts don't use the LLM — they only load data
