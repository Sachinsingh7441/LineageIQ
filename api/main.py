import sys
import os
import logging
from contextlib import asynccontextmanager
from typing import List, Dict, Any, Optional
import requests

# Add the parent directory to sys.path to allow imports from config and rag
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from config import (
    API_HOST,
    API_PORT,
    NEO4J_URI,
    NEO4J_USER,
    NEO4J_PASSWORD,
    OLLAMA_BASE_URL,
    CHROMA_PERSIST_DIR
)

# We import the agent to handle /api/ask queries directly
try:
    from rag.agent import ask
except ImportError as e:
    logging.warning(f"Could not import rag.agent.ask: {e}")
    
    # Dummy fallback if agent module is not fully present
    def ask(question: str) -> Dict[str, Any]:
        return {
            "answer": "RAG Agent not found. This is a fallback response.",
            "route": "fallback",
            "sources": []
        }

try:
    from neo4j import GraphDatabase
except ImportError:
    GraphDatabase = None

# Configure logging
logging.basicConfig(
    level=logging.INFO, 
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("lineage_api")

# In-memory history of recent interactions
chat_history: List[Dict[str, Any]] = []
MAX_HISTORY_LEN = 50

# Global Neo4j Driver
neo4j_driver = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle events for FastAPI to initialize and clean up resources."""
    global neo4j_driver
    logger.info("Starting up LineageIQ API...")
    
    if GraphDatabase:
        try:
            neo4j_driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
            # Verify connectivity on startup
            neo4j_driver.verify_connectivity()
            logger.info("Successfully connected to Neo4j graph database.")
        except Exception as e:
            logger.error(f"Failed to connect to Neo4j on startup: {e}")
            neo4j_driver = None
    else:
        logger.warning("neo4j module not installed. Graph database features will be disabled.")
        
    yield
    
    logger.info("Shutting down LineageIQ API...")
    if neo4j_driver:
        neo4j_driver.close()
        logger.info("Closed Neo4j connection.")

# Initialize FastAPI App
app = FastAPI(
    title="LineageIQ API", 
    description="API for the LineageIQ RAG Agent",
    version="1.0.0",
    lifespan=lifespan
)

# Allow CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request/Response Models
class AskRequest(BaseModel):
    question: str

class AskResponse(BaseModel):
    answer: str
    route: str
    sources: List[Any]

# Request logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    logger.info(f"Incoming request: {request.method} {request.url.path}")
    response = await call_next(request)
    logger.info(f"Completed request: {request.method} {request.url.path} with status {response.status_code}")
    return response

@app.post("/api/ask", response_model=AskResponse)
async def ask_question(req: AskRequest):
    """
    Submit a question to the RAG agent and return the response.
    The response contains the answer, routing strategy used, and sources.
    """
    try:
        logger.info(f"Processing question: {req.question}")
        
        # Call the agent
        result = ask(req.question)
        
        # Ensure result matches expected format
        response = AskResponse(
            answer=result.get("answer", "No answer provided by agent."),
            route=result.get("route", "unknown"),
            sources=result.get("sources", [])
        )
        
        # Save to history
        chat_history.append({
            "question": req.question,
            "answer": response.answer,
            "route": response.route
        })
        if len(chat_history) > MAX_HISTORY_LEN:
            chat_history.pop(0)
            
        return response
    except Exception as e:
        logger.error(f"Error executing agent ask: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Agent execution failed: {str(e)}")

@app.get("/api/health")
async def health_check():
    """
    Check the health and connectivity of the backend systems:
    Neo4j, ChromaDB, and Ollama.
    """
    health_status = {
        "status": "ok",
        "neo4j": "unknown",
        "chroma": "unknown",
        "ollama": "unknown"
    }
    
    # Check Neo4j
    if neo4j_driver:
        try:
            neo4j_driver.verify_connectivity()
            health_status["neo4j"] = "ok"
        except Exception:
            health_status["neo4j"] = "error"
            health_status["status"] = "degraded"
    else:
        health_status["neo4j"] = "not_installed"
        
    # Check Ollama
    try:
        resp = requests.get(OLLAMA_BASE_URL, timeout=2.0)
        if resp.status_code == 200:
            health_status["ollama"] = "ok"
        else:
            health_status["ollama"] = "error"
            health_status["status"] = "degraded"
    except Exception:
        health_status["ollama"] = "error"
        health_status["status"] = "degraded"
        
    # Check Chroma (local filesystem check for persistent storage)
    if os.path.exists(CHROMA_PERSIST_DIR) and os.path.isdir(CHROMA_PERSIST_DIR):
        health_status["chroma"] = "ok"
    else:
        health_status["chroma"] = "not_found"
        
    return health_status

@app.get("/api/schema")
async def get_schema():
    """
    Returns a summary of the graph schema (nodes and relationships)
    by querying Neo4j directly.
    """
    if not neo4j_driver:
        raise HTTPException(status_code=503, detail="Neo4j driver is not initialized or connected")
        
    try:
        with neo4j_driver.session() as session:
            # Retrieve node counts by label
            nodes_query = "MATCH (n) RETURN labels(n)[0] AS label, count(n) AS count"
            nodes_res = session.run(nodes_query)
            nodes = [{"label": record["label"], "count": record["count"]} for record in nodes_res if record["label"]]
            
            # Retrieve relationship counts by type
            rels_query = "MATCH ()-[r]->() RETURN type(r) AS type, count(r) AS count"
            rels_res = session.run(rels_query)
            relationships = [{"type": record["type"], "count": record["count"]} for record in rels_res if record["type"]]
            
            return {
                "nodes": nodes,
                "relationships": relationships
            }
    except Exception as e:
        logger.error(f"Failed to fetch schema from Neo4j: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@app.get("/api/history")
async def get_history():
    """
    Returns the recent question/answer history (up to 50 items) stored in memory.
    """
    return {"history": chat_history}

if __name__ == "__main__":
    logger.info(f"Starting uvicorn server on {API_HOST}:{API_PORT}")
    uvicorn.run("api.main:app", host=API_HOST, port=API_PORT, reload=True)
