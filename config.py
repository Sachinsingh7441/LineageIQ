"""
Shared Configuration for LineageIQ
==========================================

Central place for all connection strings, model names, and settings.
Each component imports from here instead of hardcoding values.

To override any setting, set the corresponding environment variable
before running the scripts. For example:
    export NEO4J_URI=bolt://my-server:7687
    export OLLAMA_MODEL=mistral
"""

import os

# =============================================================================
# Neo4j — Graph Database
# =============================================================================
# Default assumes Neo4j is running via docker-compose.yml
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "lineage123")

# =============================================================================
# Chroma — Vector Database
# =============================================================================
# Chroma can run in-process (persist to disk) or as a server.
# We use persistent local mode — no separate server needed.
CHROMA_PERSIST_DIR = os.getenv(
    "CHROMA_PERSIST_DIR",
    os.path.join(os.path.dirname(__file__), "data", "chroma_db"),
)
CHROMA_COLLECTION_NAME = os.getenv("CHROMA_COLLECTION_NAME", "lineage_metadata")

# =============================================================================
# Ollama — Local LLM
# =============================================================================
# Ollama runs locally and serves models via HTTP.
# Install: https://ollama.ai  →  then:  ollama pull llama3.1
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.1")

# =============================================================================
# Embedding Model
# =============================================================================
# We use sentence-transformers for local embeddings (no API key needed).
# This model runs on CPU and produces 384-dimensional vectors.
EMBEDDING_MODEL_NAME = os.getenv(
    "EMBEDDING_MODEL_NAME", "all-MiniLM-L6-v2"
)

# =============================================================================
# Kafka / Redpanda — Streaming (Phase 2)
# =============================================================================
KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
KAFKA_TOPIC = os.getenv("KAFKA_TOPIC", "lineage-events")
KAFKA_CONSUMER_GROUP = os.getenv("KAFKA_CONSUMER_GROUP", "lineage-consumer-group")

# =============================================================================
# FastAPI — API Server (Phase 4)
# =============================================================================
API_HOST = os.getenv("API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("API_PORT", "8000"))

# =============================================================================
# Data Paths
# =============================================================================
DATA_DIR = os.path.join(os.path.dirname(__file__), "data", "synthetic")
