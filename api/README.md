# ⚡ API Module — FastAPI REST Backend

## Overview

This module wraps the RAG agent as a **REST API**, enabling the Streamlit UI (or any other client) to interact with the system over HTTP.

| Endpoint | Method | Purpose |
|---|---|---|
| `/api/ask` | POST | Submit a question and get an answer |
| `/api/health` | GET | Check system health (Neo4j, Chroma, Ollama) |
| `/api/schema` | GET | Get graph schema summary (node/relationship counts) |
| `/api/history` | GET | Get recent question/answer history |

---

## Technologies Used

### FastAPI (Web Framework)

**What it is**: FastAPI is a modern, high-performance Python web framework for building APIs. It's designed to be:
- **Fast**: Built on Starlette (async) and Pydantic (data validation)
- **Auto-documented**: Automatically generates interactive API docs
- **Type-safe**: Uses Python type hints for request/response validation

**Why FastAPI over Flask/Django?**:
- Automatic OpenAPI documentation (Swagger UI)
- Native async support (handles concurrent requests efficiently)
- Built-in data validation via Pydantic
- Minimal boilerplate — a working API in ~50 lines

**How it works**:
```python
from fastapi import FastAPI

app = FastAPI()

@app.post("/api/ask")
async def ask_question(req: AskRequest):
    result = agent.ask(req.question)
    return AskResponse(answer=result["answer"], ...)
```

### Pydantic (Data Validation)

**What it is**: A Python library that validates data using type hints. In FastAPI, Pydantic models define what the API expects and returns.

**Our models**:
```python
class AskRequest(BaseModel):
    question: str          # Must be a string

class AskResponse(BaseModel):
    answer: str            # The LLM's answer
    route: str             # Which strategy was used (cypher/vector/hybrid)
    sources: List[Any]     # Evidence used to generate the answer
```

If a client sends invalid data (e.g., missing `question`), Pydantic automatically returns a 422 Validation Error with a helpful message.

### Uvicorn (ASGI Server)

**What it is**: Uvicorn is a lightning-fast **ASGI server** for Python. ASGI (Asynchronous Server Gateway Interface) is the async successor to WSGI.

**How we use it**: FastAPI is the framework; Uvicorn is what actually serves HTTP requests:
```python
uvicorn.run("api.main:app", host="0.0.0.0", port=8000, reload=True)
```

### CORS (Cross-Origin Resource Sharing)

**What it is**: A browser security feature that blocks web pages from making requests to a different domain. We configure CORS to allow all origins during development:
```python
app.add_middleware(CORSMiddleware, allow_origins=["*"])
```

This lets the Streamlit UI (running on port 8501) call the API (running on port 8000).

---

## API Endpoints

### `POST /api/ask` — Ask a Question

**Request**:
```json
{
    "question": "What tables feed into curated_orders?"
}
```

**Response**:
```json
{
    "answer": "curated_orders depends on three staging tables: stg_orders, stg_payments, and stg_shipping.",
    "route": "cypher",
    "sources": [
        "Neo4j Graph Database",
        "Cypher used: MATCH (t:Table {name: 'curated_orders'})-[:DEPENDS_ON]->(up:Table) RETURN up.name"
    ]
}
```

### `GET /api/health` — System Health Check

**Response**:
```json
{
    "status": "ok",
    "neo4j": "ok",
    "chroma": "ok",
    "ollama": "ok"
}
```

Possible states: `ok`, `error`, `not_installed`, `not_found`, `degraded`

### `GET /api/schema` — Graph Schema Summary

**Response**:
```json
{
    "nodes": [
        {"label": "Table", "count": 22},
        {"label": "Column", "count": 170},
        {"label": "Job", "count": 21},
        {"label": "JobRun", "count": 190}
    ],
    "relationships": [
        {"type": "HAS_COLUMN", "count": 170},
        {"type": "READS_FROM", "count": 24},
        {"type": "WRITES_TO", "count": 22},
        {"type": "DEPENDS_ON", "count": 19},
        {"type": "RUN_OF", "count": 190}
    ]
}
```

### `GET /api/history` — Recent Q&A History

Returns the last 50 question/answer pairs stored in memory.

**Response**:
```json
{
    "history": [
        {
            "question": "What tables feed into curated_orders?",
            "answer": "...",
            "route": "cypher"
        }
    ]
}
```

---

## Running the API

### Start the Server
```bash
python api/main.py
```

The server starts on `http://0.0.0.0:8000` with hot-reload enabled.

### Interactive API Documentation
Once the server is running, visit:
- **Swagger UI**: [http://localhost:8000/docs](http://localhost:8000/docs) — interactive API explorer
- **ReDoc**: [http://localhost:8000/redoc](http://localhost:8000/redoc) — alternative documentation

### Test with curl
```bash
# Health check
curl http://localhost:8000/api/health

# Ask a question
curl -X POST http://localhost:8000/api/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "What tables feed into curated_orders?"}'
```

---

## Architecture Notes

### Lifecycle Management
The API uses FastAPI's **lifespan** context manager to:
- **On startup**: Initialize the Neo4j driver and verify connectivity
- **On shutdown**: Close the Neo4j driver cleanly (release connections)

### Error Handling
- If the RAG agent raises an exception, the API returns a **500 Internal Server Error** with the error details
- If Neo4j is not connected, schema endpoints return **503 Service Unavailable**
- Invalid request bodies return **422 Validation Error** (automatic via Pydantic)

### Request Logging
Every incoming request is logged with method, path, and response status code via middleware.

---

## Prerequisites

- **Ollama** running with `llama3.1` model
- **Neo4j** running with data loaded
- **Chroma** populated with embeddings
- **Python packages**: `fastapi`, `uvicorn`, `pydantic`, `requests`, `neo4j`
