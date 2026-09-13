# 💬 UI Module — Streamlit Chat Interface

## Overview

This module provides the **user-facing chat interface** for LineageIQ. Users type questions in plain English and get answers with source citations, all through a web-based chat UI.

---

## Technology Used

### Streamlit (UI Framework)

**What it is**: Streamlit is a Python framework that lets you build interactive web applications **without writing any HTML, CSS, or JavaScript**. You write Python, and Streamlit renders it as a web app.

**Why Streamlit?**:
- **Fastest path to a UI**: Build a working chat interface in ~200 lines of Python
- **No frontend skills needed**: Perfect for data engineers and ML engineers
- **Built-in components**: Chat messages, buttons, sidebars, spinners, expanders
- **Hot reload**: Changes to the Python file are instantly reflected in the browser

**How it works**:
1. You write a Python script using Streamlit's API
2. Run it with `streamlit run ui/app.py`
3. Streamlit starts a web server and renders your script as an interactive web page
4. When a user interacts (clicks, types), Streamlit **re-runs the entire script** from top to bottom

**Key concept — Session State**: Since Streamlit re-runs the script on every interaction, you need `st.session_state` to persist data (like chat history) across reruns:
```python
# This persists across reruns
if "messages" not in st.session_state:
    st.session_state.messages = []

# This would reset on every rerun (wrong!)
messages = []
```

---

## Features

### Chat Interface
- **Chat-style messages**: User questions and assistant answers displayed as chat bubbles
- **Persistent history**: Messages survive across interactions using `st.session_state`
- **Thinking spinner**: Shows "Thinking..." while the agent processes a question

### Sidebar
| Section | What it Shows |
|---|---|
| **Settings** | Execution mode selector (Direct vs API) |
| **System Status** | Green/red indicators for Neo4j, Chroma, Ollama, API |
| **Sample Questions** | 5 clickable example questions to get started |

### Response Enrichment
Each answer includes:
- **Route badge**: Shows whether `CYPHER`, `VECTOR`, or `HYBRID` strategy was used (color-coded)
- **Sources expander**: Click "View Sources" to see the Cypher query used, graph paths, or retrieved documents

### Two Execution Modes

| Mode | How it Works | When to Use |
|---|---|---|
| **Direct Mode** | Imports `rag.agent.ask()` directly — runs in the same process | Default. Simpler setup, no separate API needed. |
| **API Mode** | Calls `POST http://localhost:8000/api/ask` over HTTP | When running the FastAPI server separately (production-like). |

The UI defaults to **Direct Mode** since you might not have the API server running initially.

---

## How It Works (Code Walkthrough)

### 1. Page Configuration
```python
st.set_page_config(page_title="LineageIQ", page_icon="🧬", layout="wide")
st.title("🧬 LineageIQ")
```

### 2. System Status Checks
The sidebar checks connectivity to all backend systems:
- **API Mode**: Calls `GET /api/health` on the FastAPI server
- **Direct Mode fallback**: Uses socket connections (Neo4j), filesystem checks (Chroma), and HTTP pings (Ollama)

Status indicators use colored circles:
- 🟢 Green = Connected
- 🔴 Red = Error
- ⚪ Gray = Unknown

### 3. Sample Questions
Five pre-written questions appear as buttons in the sidebar. Clicking one auto-fills the chat input:
```python
if st.button("What tables feed into curated_orders?"):
    st.session_state.queued_question = "What tables feed into curated_orders?"
```

### 4. Chat Message Loop
Renders all historical messages from `st.session_state.messages`:
```python
for message in st.session_state.messages:
    with st.chat_message(message["role"]):  # "user" or "assistant"
        st.markdown(message["content"])
```

### 5. Question Processing
When the user types or clicks a sample question:
1. Display the question in a user chat bubble
2. Show a "Thinking..." spinner
3. Call the agent (directly or via API)
4. Display the answer in an assistant chat bubble
5. Show the route badge and sources
6. Save everything to session state

### 6. Error Handling
- **API connection failure**: Shows a red error message suggesting to check if the backend is running
- **Agent failure**: Displays the exception message in the chat

---

## Running the UI

### Quick Start (Direct Mode)
```bash
streamlit run ui/app.py
```
Opens at [http://localhost:8501](http://localhost:8501)

### With API Backend
```bash
# Terminal 1: Start API
python api/main.py

# Terminal 2: Start UI
streamlit run ui/app.py
# Switch to "API Mode" in the sidebar
```

### Streamlit Configuration
Streamlit can be configured via `~/.streamlit/config.toml` or CLI flags:
```bash
# Run on a different port
streamlit run ui/app.py --server.port 8502

# Disable file watcher (for production)
streamlit run ui/app.py --server.fileWatcherType none
```

---

## UI Architecture

```
┌─────────────────────────────────────────────────────┐
│                   Streamlit UI                       │
│  ┌──────────┐  ┌─────────────────────────────────┐  │
│  │ Sidebar   │  │ Main Chat Area                   │  │
│  │           │  │                                   │  │
│  │ Settings  │  │  User: "What feeds into...?"     │  │
│  │ Status    │  │                                   │  │
│  │ Samples   │  │  Assistant: "curated_orders       │  │
│  │           │  │  depends on stg_orders..."        │  │
│  │           │  │  [CYPHER] [▶ View Sources]        │  │
│  │           │  │                                   │  │
│  │           │  │  [Type your question here...]     │  │
│  └──────────┘  └─────────────────────────────────┘  │
│                                                      │
│         ↓ Direct Mode        ↓ API Mode              │
│    rag.agent.ask()     POST /api/ask                 │
└─────────────────────────────────────────────────────┘
```

---

## Prerequisites

- **Streamlit**: `pip install streamlit`
- **Requests**: `pip install requests` (for API mode)
- **For Direct Mode**: All RAG dependencies (LangChain, Ollama, Neo4j, Chroma) must be installed
- **For API Mode**: The FastAPI server must be running (`python api/main.py`)
