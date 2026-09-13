# Project Plan: Real-Time LineageIQ (GraphRAG + Streaming)

**Goal:** Build a natural-language assistant that answers questions about data lineage — "what feeds into table X?", "why did this pipeline fail last night?", "what breaks if I change column Y?" — by combining a knowledge graph (Neo4j), a vector database, an LLM, and a Kafka streaming layer that keeps the lineage graph updated in near-real-time.

This single project is designed to close **both** of your stated gaps — GenAI/RAG/vector DB and streaming — in one coherent system, because it mirrors the professional problem you already own (lineage) rather than a generic tutorial clone.

---

## 1. What You're Building (Plain-English Description)

A pipeline emits events ("job X ran," "table Y was written," "column Z changed") onto a Kafka topic. A streaming consumer picks these up, updates a Neo4j lineage graph in near-real-time, and also generates embeddings for new/changed metadata into a vector database. A user asks a question in plain English through a simple chat interface. The system:

1. Retrieves relevant context — either by converting the question into a Cypher query against Neo4j (structural/relationship questions), or by doing a similarity search against the vector DB (descriptive/semantic questions), or both.
2. Passes the retrieved context to an LLM.
3. Returns a natural-language answer, optionally with the underlying graph path shown.

This is a **GraphRAG** pattern (RAG over a graph, not just flat documents) with a **streaming ingestion layer** — a combination most candidates won't have on their resume.

---

## 2. Architecture

```
                         ┌─────────────────────┐
  Simulated pipeline  →  │   Kafka topic         │
  events (job runs,      │   "lineage-events"    │
  schema changes)        └──────────┬───────────┘
                                     │
                          ┌──────────▼───────────┐
                          │  Streaming Consumer    │
                          │  (Spark Structured      │
                          │   Streaming or plain     │
                          │   Kafka consumer)         │
                          └──────────┬───────────┘
                                     │
                    ┌────────────────┼────────────────┐
                    ▼                                  ▼
          ┌──────────────────┐              ┌──────────────────────┐
          │  Neo4j Graph DB    │              │  Embedding step        │
          │  (lineage graph:    │              │  (table/column          │
          │   tables, jobs,       │              │   descriptions →        │
          │   columns, edges)      │              │   vector DB)             │
          └──────────────────┘              └──────────────────────┘
                    │                                  │
                    └────────────────┬────────────────┘
                                      ▼
                         ┌─────────────────────────┐
                         │   RAG / Agent Layer          │
                         │   - text-to-Cypher              │
                         │   - vector similarity search      │
                         │   - LLM answer synthesis            │
                         └──────────────┬───────────┘
                                        ▼
                         ┌─────────────────────────┐
                         │   Chat UI (Streamlit/         │
                         │   simple web app)                │
                         └─────────────────────────┘
```

---

## 3. Data: What You'll Actually Use

You don't need — and shouldn't use — real Accenture data. Build a synthetic but realistic dataset:

- **Synthetic data warehouse schema:** invent a fictional e-commerce or banking data warehouse — 15–30 tables (e.g., `orders`, `customers`, `payments`, `shipping_events`, staging tables, curated tables), each with a handful of columns and short descriptions.
- **Synthetic pipeline/job metadata:** 10–20 "jobs" that read from some tables and write to others (this defines your lineage edges).
- **Synthetic event stream:** a script that periodically emits JSON events like `{"job": "load_orders", "reads": ["stg_orders"], "writes": ["curated_orders"], "status": "success", "timestamp": ...}` onto a Kafka topic — this simulates a real pipeline orchestrator emitting lineage events.
- **Column/table descriptions:** short natural-language descriptions per table/column (you write these) — these get embedded into the vector DB and are what makes the semantic-search half of the system work.

Tip: generate this with a script (Python + Faker library) so it's reproducible and you can point to the generator in your GitHub repo — that itself is a small demonstration of engineering care.

---

## 4. Build Phases (Suggested ~8–10 Week Plan, Part-Time)

**Phase 0 — Learning (Weeks 1–2, can overlap with Phase 1)**
Learn Kafka fundamentals and enough LLM/RAG concepts to start. See resources in Section 6.

**Phase 1 — Static Graph + Basic RAG (Weeks 2–3)**
- Stand up Neo4j (Docker is easiest locally).
- Load your synthetic schema/lineage as a static graph (no streaming yet).
- Build a basic vector DB index (Chroma is the fastest to start with) over your table/column descriptions.
- Build a simple text-to-Cypher chain: user question → LLM generates Cypher → query Neo4j → LLM formats the answer.
- Get a working end-to-end query answering *one* question type before adding complexity.

**Phase 2 — Add Kafka Streaming (Weeks 4–5)**
- Set up Kafka locally (Docker Compose — Confluent or Redpanda both work and are easy to run locally).
- Write a producer script that emits synthetic lineage events at intervals.
- Write a consumer (start with a plain Python `kafka-python` consumer; upgrade to Spark Structured Streaming once the plain version works) that:
  - Updates the Neo4j graph based on incoming events (new nodes/edges, or marks a job run as failed).
  - Re-embeds any new/changed table descriptions into the vector DB.
- This is the part that demonstrates real streaming competence — show before/after: "graph updates within X seconds of an event."

**Phase 3 — RAG/Agent Layer Maturity (Weeks 6–7)**
- Improve the routing logic: some questions need Cypher (structural — "what depends on table X"), some need vector search (semantic — "which tables relate to customer refunds"), some need both. Build simple routing logic or use an agent framework (LangChain/LlamaIndex) to decide.
- Add answer grounding: show the actual graph path or retrieved chunks alongside the LLM's answer (this matters a lot in interviews — it shows you understand RAG isn't just "trust the LLM").
- Handle a "why did X fail" question type using the job-status data from your streaming events.

**Phase 4 — Polish, UI, Deployment (Week 8+)**
- Build a minimal Streamlit chat UI.
- Deploy locally or on a free-tier cloud option (Streamlit Community Cloud, or a small EC2/GCP free-tier instance since you're GCP-certified).
- Write a clear README with an architecture diagram (reuse the one above) and a demo GIF/video.
- Push to GitHub with a clean commit history — this becomes your portfolio artifact and interview talking point.

---

## 5. Tech Stack (Recommended, With Reasoning)

| Layer | Recommended Choice | Why |
|---|---|---|
| Streaming | **Apache Kafka** (via Redpanda or Confluent, Docker) | Industry-standard; directly closes your stated gap |
| Stream processing | Start with plain Python consumer → upgrade to **Spark Structured Streaming** | You already know Spark — Structured Streaming reuses that mental model, so this is your fastest path to real depth, not just familiarity |
| Graph DB | **Neo4j** (you already know this) | Reuse existing expertise; this is your differentiator |
| Vector DB | **Chroma** (to start) or **pgvector** (if you want to also show Postgres integration, which you already use professionally) | Chroma has the lowest setup friction; pgvector is a stronger resume signal if you want to lean into your existing Postgres experience |
| LLM | **Anthropic Claude API** or **OpenAI API** (paid, cheap for small projects) or a local open-source model via **Ollama** (free) | Use a hosted API for reliability while learning; mention you evaluated a local option too if you try Ollama |
| Orchestration/RAG framework | **LangChain** or **LlamaIndex** (pick one, don't learn both) | Both are widely recognized; LlamaIndex has slightly better native graph/RAG support if you want less custom code |
| API layer | **FastAPI** | Lightweight, Python-native, easy to demo |
| UI | **Streamlit** | Fastest way to get a usable chat interface without frontend work |

---

## 6. Learning Resources

### Kafka (streaming — your primary new gap)
- **Confluent's free "Kafka 101" course** (confluent.io/learn/kafka-101) — the most widely used starting point, built by the company behind Kafka, hands-on and practical.
- **Official Apache Kafka documentation Quickstart** (kafka.apache.org/documentation/#quickstart) — for running Kafka locally and understanding topics/partitions/consumer groups.
- **Redpanda's "Kafka in 5 minutes" and free courses** — a Kafka-compatible alternative that's much easier to run locally in Docker; good if Kafka setup itself becomes a blocker.

### Spark Structured Streaming (extends your existing Spark knowledge)
- **Official Spark Structured Streaming Programming Guide** (spark.apache.org/docs/latest/structured-streaming-programming-guide.html) — since you already know batch Spark, this is the fastest way to see exactly what changes for streaming.
- **Databricks Academy free Structured Streaming content** — Databricks (whose certification you already hold) has free self-paced content specifically on streaming; check their Learning platform since you already have an account from your certification.

### Vector Databases & Embeddings
- **Chroma's own "Getting Started" docs** (docs.trychroma.com) — simplest to follow for a first vector DB.
- **pgvector GitHub README** (github.com/pgvector/pgvector) — if you choose Postgres-based vectors instead.
- **"Embeddings" guide from OpenAI or Anthropic's documentation** — both providers publish clear conceptual explanations of what embeddings are and how similarity search works.

### RAG / LLM Agents / LangChain / LlamaIndex
- **LangChain official documentation + their free "LangChain Academy" course** (academy.langchain.com) — structured, free, and current.
- **LlamaIndex official documentation "Understanding" section** — particularly their guides on knowledge graphs and GraphRAG specifically, which is directly relevant to your project.
- **DeepLearning.AI's short free courses** (deeplearning.ai/short-courses) — search for "RAG," "LangChain," and "Building Agentic RAG" — these are free, 1–2 hour courses built with Anthropic/OpenAI/LangChain teams and are widely respected on resumes and in interviews.

### GraphRAG specifically (your most differentiating piece)
- **Microsoft's GraphRAG research paper and open-source repo** (github.com/microsoft/graphrag) — even if you don't use their exact implementation, understanding their approach to combining graphs with RAG will directly inform your design.
- **Neo4j's own GraphRAG documentation and blog series** (neo4j.com/generativeai or their developer blog) — since you already use Neo4j professionally, their own guides on combining Neo4j with LLMs are the most directly applicable resource you'll find.

---

## 7. How to Present This on Your Resume (Once Built)

Once you have a working version — even before Phase 4 polish — you can add a real Projects bullet. Example shape (fill in your actual numbers once you have them):

> **LineageIQ (Personal Project)** - Built a GraphRAG-based natural language assistant over a Neo4j lineage graph, combining a Kafka streaming ingestion layer (updating the graph in near-real-time from simulated pipeline events) with vector-based semantic search and LLM-generated Cypher queries to answer lineage questions in plain English. [Add a real metric once you have one - e.g., "graph updates within X seconds of an event" or "correctly answered X% of a test question set."]

Don't add this to your resume until you have something real to say about it in an interview — an unfinished project bullet is worse than no bullet, for the same reason the earlier placeholder text was a problem.

---

## 8. A Note on Scope

This is a genuinely ambitious project — don't feel obligated to build every phase before it's "resume-worthy." A working Phase 1 + Phase 2 (static graph RAG + basic Kafka streaming updating it) is already a strong, differentiated portfolio piece and closes both of your stated gaps. Phases 3–4 are what take it from "solid" to "impressive in an interview," and you can keep iterating on those even after you've started applying.
