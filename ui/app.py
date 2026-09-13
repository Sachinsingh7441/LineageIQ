import sys
import os
import requests
import json
import streamlit as st

# Add the parent directory to sys.path to allow imports from config and rag
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import API_HOST, API_PORT, NEO4J_URI, CHROMA_PERSIST_DIR, OLLAMA_BASE_URL

# Try importing the agent directly for 'Direct Mode' fallback
try:
    from rag.agent import ask as direct_agent_ask
    HAS_DIRECT_AGENT = True
except ImportError:
    HAS_DIRECT_AGENT = False
    direct_agent_ask = None

# Resolve 0.0.0.0 to localhost for outbound HTTP requests (required on Windows)
_client_host = "localhost" if API_HOST in ("0.0.0.0", "") else API_HOST
API_URL = f"http://{_client_host}:{API_PORT}"

def check_system_status():
    """Check the status of backend systems by calling the API health endpoint."""
    try:
        response = requests.get(f"{API_URL}/api/health", timeout=2.0)
        if response.status_code == 200:
            return response.json()
    except Exception:
        pass
    
    # Fallback to direct checks if API is down
    status = {"neo4j": "unknown", "chroma": "unknown", "ollama": "unknown", "api": "offline"}
    try:
        import socket
        from urllib.parse import urlparse
        
        # Check Neo4j simple socket connection
        parsed_neo4j = urlparse(NEO4J_URI)
        host, port = parsed_neo4j.hostname or 'localhost', parsed_neo4j.port or 7687
        with socket.create_connection((host, port), timeout=1.0):
            status["neo4j"] = "ok"
    except Exception:
        status["neo4j"] = "error"
        
    if os.path.exists(CHROMA_PERSIST_DIR):
        status["chroma"] = "ok"
    else:
        status["chroma"] = "not_found"
        
    try:
        if requests.get(OLLAMA_BASE_URL, timeout=1.0).status_code == 200:
            status["ollama"] = "ok"
    except Exception:
        status["ollama"] = "error"
        
    return status

# ==========================================
# UI Setup
# ==========================================
st.set_page_config(page_title="LineageIQ", page_icon="🧬", layout="wide")

st.title("🧬 LineageIQ")
st.markdown("Your intelligent assistant for understanding data warehouse lineage and pipelines.")

# Initialize session state for chat history
if "messages" not in st.session_state:
    st.session_state.messages = []

# ==========================================
# Sidebar Settings and Status
# ==========================================
with st.sidebar:
    st.header("⚙️ Settings")
    
    # Mode Selector
    mode_options = ["Direct Mode (In-Process)"] if HAS_DIRECT_AGENT else []
    mode_options.insert(0, "API Mode (via FastAPI)")
    
    # Default to Direct Mode if available, since API might not be running initially
    default_index = 1 if HAS_DIRECT_AGENT else 0
    mode = st.radio("Execution Mode", options=mode_options, index=default_index)
    
    st.divider()
    
    # System Status
    st.header("🟢 System Status")
    status = check_system_status()
    
    def status_indicator(name, state):
        color = "green" if state == "ok" else "red" if state == "error" else "gray"
        return f":{color}[●] {name}"
        
    st.markdown(status_indicator("API Server", status.get("api", "ok") if status.get("status") == "ok" else status.get("api", "error")))
    st.markdown(status_indicator("Neo4j Graph", status.get("neo4j", "unknown")))
    st.markdown(status_indicator("ChromaDB", status.get("chroma", "unknown")))
    st.markdown(status_indicator("Ollama LLM", status.get("ollama", "unknown")))

    st.divider()
    
    # Sample Questions
    st.header("💡 Sample Questions")
    sample_questions = [
        "What tables feed into curated_orders?",
        "Which tables relate to customer refunds?",
        "What happens if I change raw_payments?",
        "Did any jobs fail recently?",
        "Explain the lineage of the daily sales report"
    ]
    
    for q in sample_questions:
        if st.button(q, use_container_width=True):
            # Send sample question when clicked
            st.session_state.queued_question = q

# ==========================================
# Chat Interface
# ==========================================
# Display chat messages from history
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        
        if "route" in message and "sources" in message:
            route = message["route"]
            sources = message["sources"]
            
            # Show route badge
            route_color = "blue" if route == "cypher" else "green" if route == "vector" else "purple"
            st.markdown(f"**Route used:** :{route_color}[{route.upper()}]")
            
            # Show sources expander
            if sources:
                with st.expander("View Sources"):
                    st.json(sources)

# Check if a sample question was queued
question = st.chat_input("Ask a question about your data warehouse lineage...")
if "queued_question" in st.session_state:
    question = st.session_state.queued_question
    del st.session_state.queued_question

if question:
    # Display user question
    with st.chat_message("user"):
        st.markdown(question)
    st.session_state.messages.append({"role": "user", "content": question})

    # Call backend and get answer
    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            try:
                answer = "An error occurred."
                route = "error"
                sources = []
                
                if mode == "API Mode (via FastAPI)":
                    # Call API
                    response = requests.post(
                        f"{API_URL}/api/ask", 
                        json={"question": question},
                        timeout=30.0
                    )
                    response.raise_for_status()
                    data = response.json()
                    answer = data.get("answer", "No answer provided.")
                    route = data.get("route", "unknown")
                    sources = data.get("sources", [])
                else:
                    # Direct import execution
                    if HAS_DIRECT_AGENT and direct_agent_ask:
                        result = direct_agent_ask(question)
                        answer = result.get("answer", "No answer provided.")
                        route = result.get("route", "unknown")
                        sources = result.get("sources", [])
                    else:
                        answer = "Direct mode unavailable. Please switch to API mode."
                
                # Render answer
                st.markdown(answer)
                
                # Show metadata
                route_color = "blue" if route == "cypher" else "green" if route == "vector" else "purple"
                st.markdown(f"**Route used:** :{route_color}[{route.upper()}]")
                if sources:
                    with st.expander("View Sources"):
                        st.json(sources)
                
                # Save to history
                st.session_state.messages.append({
                    "role": "assistant", 
                    "content": answer,
                    "route": route,
                    "sources": sources
                })
                
            except requests.exceptions.RequestException as e:
                error_msg = f"Failed to connect to API. Is the backend running? ({e})"
                st.error(error_msg)
                st.session_state.messages.append({"role": "assistant", "content": error_msg})
            except Exception as e:
                error_msg = f"An error occurred: {e}"
                st.error(error_msg)
                st.session_state.messages.append({"role": "assistant", "content": error_msg})
