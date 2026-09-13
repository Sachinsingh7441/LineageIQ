# 🧠 RAG Module — Intelligence Layer

## Overview

This is the **brain** of LineageIQ. It takes a plain-English question, figures out the best way to answer it, retrieves relevant context from the graph and/or vector databases, and synthesizes a natural-language response.

| Component | Purpose |
|---|---|
| `router.py` | Classifies the question type (structural vs semantic vs both) |
| `cypher_chain.py` | Converts questions to Cypher graph queries |
| `vector_search.py` | Finds semantically similar metadata |
| `agent.py` | Orchestrates everything into a single `ask()` function |

---

## Technologies Used

### LangChain (RAG Framework)
**What it is**: LangChain is a Python framework for building applications powered by Large Language Models. It provides building blocks that chain together:

```
Prompt Template → LLM → Output Parser → Next Step
```

**Key concepts we use**:
- **PromptTemplate**: A string template with variables (like `{question}`) that gets filled in at runtime
- **ChatOllama**: A LangChain wrapper around Ollama that treats the local LLM as a chat model
- **StrOutputParser**: Extracts the raw string from the LLM's response
- **Chain (|)**: The pipe operator chains components together: `prompt | llm | parser`

**Example from our code**:
```python
# Define the template
prompt = PromptTemplate(
    input_variables=["question"],
    template="Convert this to Cypher: {question}"
)

# Chain: template → LLM → string output
chain = prompt | ChatOllama(model="llama3.1") | StrOutputParser()

# Run it
cypher = chain.invoke({"question": "What tables feed into curated_orders?"})
# → "MATCH (t:Table {name: 'curated_orders'})-[:DEPENDS_ON]->(up:Table) RETURN up.name"
```

### Ollama (Local LLM)
**What it is**: Ollama runs Large Language Models **locally on your machine**. No cloud API, no costs, no data leaving your computer.

**How it works**:
1. You download a model: `ollama pull llama3.1`
2. Ollama serves it via HTTP at `http://localhost:11434`
3. Our code sends prompts to this local server and gets responses back

**Model we use**: `llama3.1` (8B parameter model by Meta — ~4.7GB download)

**Why local?**: 
- **Free** — no API credits needed
- **Private** — data stays on your machine
- **Offline** — works without internet after model download

### Neo4j Cypher (Graph Query Language)
**What it is**: Cypher is a declarative query language for graph databases, similar to SQL but designed for traversing relationships.

**Key patterns**:
```cypher
-- Find a node
MATCH (t:Table {name: 'curated_orders'})

-- Traverse a relationship
MATCH (j:Job)-[:READS_FROM]->(t:Table)

-- Multi-hop traversal (follow dependencies recursively)
MATCH (t:Table)-[:DEPENDS_ON*1..]->(upstream:Table)

-- Filter and return
WHERE jr.status = 'failed'
RETURN j.name, jr.error_message
```

### Prompt Engineering
**What it is**: The art of crafting instructions for an LLM to get reliable, useful outputs. Our prompts include:
- **System context**: "You are an expert Neo4j Cypher developer for a data lineage system"
- **Schema definition**: Full list of node types, properties, and relationships
- **Few-shot examples**: 5+ example question→query pairs for the LLM to learn from
- **Output constraints**: "Only respond with the Cypher query. No explanations."

---

## Component Details

### `router.py` — Question Classification

**Purpose**: Determines the best strategy to answer a question before any expensive operations happen.

**Three route types**:

| Route | When Used | Example Questions |
|---|---|---|
| `cypher` | Structural/relationship questions | "What feeds into curated_orders?" |
| `vector` | Semantic/descriptive questions | "Which tables relate to customer refunds?" |
| `hybrid` | Needs both structural AND semantic | "Explain the lineage of the daily sales report and what it contains" |

**How it works**:
1. **Primary**: Sends the question to the LLM with classification examples (few-shot prompting)
2. **Fallback**: If the LLM fails or returns an invalid category, uses keyword matching:
   - Cypher keywords: "feed", "depend", "upstream", "downstream", "job", "fail", "column"
   - Vector keywords: "about", "relate", "find", "search", "concept"
   - Both present → hybrid

**Run standalone**:
```bash
python rag/router.py
```

---

### `cypher_chain.py` — Text-to-Cypher Translation

**Purpose**: Converts a natural-language question into a Cypher query, executes it against Neo4j, and generates a human-readable answer.

**The three-step pipeline**:
```
Question → [LLM generates Cypher] → [Execute on Neo4j] → [LLM formats answer]
```

**Step 1 — Cypher Generation**: A detailed prompt tells the LLM about the graph schema and shows example question→Cypher pairs:
```
Question: what tables does build_curated_orders read?
Query: MATCH (j:Job {name: 'build_curated_orders'})-[:READS_FROM]->(t:Table) RETURN t.name
```

**Step 2 — Execution**: The generated Cypher runs against Neo4j using LangChain's `Neo4jGraph` wrapper.

**Step 3 — Answer Synthesis**: Another LLM call takes the raw results and formats them as a natural-language answer.

**Error recovery**: If the generated Cypher has a syntax error, the chain retries once, passing the error message to the LLM so it can self-correct.

**Run standalone**:
```bash
python rag/cypher_chain.py
```

---

### `vector_search.py` — Semantic Similarity Search

**Purpose**: Finds metadata documents (table/column descriptions) that are semantically similar to the user's question, then synthesizes an answer.

**How it works**:
```
Question → [Embed with sentence-transformers] → [Search Chroma for nearest neighbors] → [LLM synthesizes answer]
```

1. The user's question is converted to a 384-dimensional vector
2. Chroma finds the K nearest documents by cosine distance
3. The retrieved documents are formatted as context
4. The LLM generates an answer grounded in the retrieved context

**Two functions exposed**:
- `search_similar(query, n_results)` — Returns raw similar documents (no LLM)
- `search_and_answer(question, n_results)` — Searches AND synthesizes an answer

**Run standalone**:
```bash
python rag/vector_search.py
```

---

### `agent.py` — The Orchestrator

**Purpose**: The single entry point (`ask()` function) that ties everything together.

**Flow**:
```python
def ask(question: str) -> dict:
    route = classify_question(question)    # Step 1: Route

    if route == "cypher":
        result = query_graph(question)     # Step 2a: Graph query

    elif route == "vector":
        result = search_and_answer(question)  # Step 2b: Vector search

    elif route == "hybrid":
        graph_res = query_graph(question)     # Step 2c: Both
        vec_docs = search_similar(question)
        # Synthesize combined answer using both contexts

    return {
        "question": question,
        "route": route,
        "answer": "...",
        "sources": ["..."]   # What evidence was used
    }
```

**Answer grounding**: Every response includes `sources` — showing the Cypher query used, the graph paths traversed, or the documents retrieved. This proves the answer isn't hallucinated.

**Run standalone** (interactive mode):
```bash
python rag/agent.py
# Type questions, get answers. Type 'quit' to exit.
```

---

## What is RAG? (Retrieval-Augmented Generation)

Traditional LLM usage:
```
User: "What feeds into curated_orders?"
LLM:  "I'm not sure, let me guess..." (hallucination risk!)
```

RAG pattern:
```
User: "What feeds into curated_orders?"
  ↓
Retrieve: [Query Neo4j → curated_orders depends on stg_orders, stg_payments, stg_shipping]
  ↓
Generate: "Based on the graph, curated_orders depends on three staging tables: ..."
```

By **retrieving facts first**, then **generating based on those facts**, we get accurate, grounded answers.

## What is GraphRAG?

Standard RAG searches flat documents. **GraphRAG** adds a knowledge graph, enabling:
- **Relationship traversal**: "What are ALL upstream dependencies?" (multi-hop graph query)
- **Impact analysis**: "What breaks if I change this table?" (reverse traversal)
- **Structural questions**: Questions that flat document search simply can't answer

Our system combines **both** — graph queries for structure and vector search for semantics.

---

## Prerequisites

- **Ollama** running with `llama3.1` model loaded
- **Neo4j** running with data loaded (via `scripts/load_graph.py`)
- **Chroma** populated with embeddings (via `scripts/embed_metadata.py`)
- **Python packages**: `langchain`, `langchain-ollama`, `langchain-community`, `langchain-core`, `chromadb`, `sentence-transformers`, `neo4j`
