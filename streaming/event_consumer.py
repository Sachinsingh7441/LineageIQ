"""
Kafka Event Consumer for LineageIQ
========================================

Consumes events from Kafka and updates Neo4j and Chroma DB in near real-time.
Handles 'job_run' and 'schema_change' events.

Usage:
  python event_consumer.py
"""

import sys
import os
import time
import json
import logging
from datetime import datetime

# Add parent directory to path to import config
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import (
    KAFKA_BOOTSTRAP_SERVERS, KAFKA_TOPIC, KAFKA_CONSUMER_GROUP,
    NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD,
    CHROMA_PERSIST_DIR, CHROMA_COLLECTION_NAME, EMBEDDING_MODEL_NAME
)

try:
    from kafka import KafkaConsumer
    from neo4j import GraphDatabase
    import chromadb
    from sentence_transformers import SentenceTransformer
except ImportError as e:
    print(f"Import Error: {e}")
    print("Ensure kafka-python-ng, neo4j, chromadb, and sentence-transformers are installed.")
    sys.exit(1)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class LineageEventConsumer:
    """Consumes lineage events and applies them to the graph and vector databases."""
    
    def __init__(self):
        self._init_kafka()
        self._init_neo4j()
        self._init_chroma()
        
    def _init_kafka(self):
        """Initialize Kafka consumer with retries."""
        logger.info(f"Connecting to Kafka at {KAFKA_BOOTSTRAP_SERVERS}...")
        self.consumer = KafkaConsumer(
            KAFKA_TOPIC,
            bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
            group_id=KAFKA_CONSUMER_GROUP,
            auto_offset_reset='latest',
            value_deserializer=lambda m: json.loads(m.decode('utf-8'))
        )
        logger.info(f"Subscribed to topic: {KAFKA_TOPIC}")

    def _init_neo4j(self):
        """Initialize Neo4j driver."""
        logger.info(f"Connecting to Neo4j at {NEO4J_URI}...")
        self.neo4j_driver = GraphDatabase.driver(
            NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD)
        )
        # Verify connection
        self.neo4j_driver.verify_connectivity()
        logger.info("Neo4j connection successful.")

    def _init_chroma(self):
        """Initialize ChromaDB and embedding model."""
        logger.info("Initializing ChromaDB and sentence-transformers...")
        self.chroma_client = chromadb.PersistentClient(path=CHROMA_PERSIST_DIR)
        self.collection = self.chroma_client.get_or_create_collection(name=CHROMA_COLLECTION_NAME)
        self.encoder = SentenceTransformer(EMBEDDING_MODEL_NAME)
        logger.info("Vector database initialized.")

    def process_job_run(self, event):
        """Process a job_run event and update Neo4j."""
        with self.neo4j_driver.session() as session:
            # Merge Job node
            job_name = event.get('job_name')
            session.run("""
                MERGE (j:Job {name: $job_name})
            """, job_name=job_name)

            # Create JobRun node and connect it to Job
            session.run("""
                MATCH (j:Job {name: $job_name})
                CREATE (r:JobRun {
                    run_id: $run_id,
                    status: $status,
                    started_at: $timestamp,
                    duration_seconds: $duration_seconds,
                    records_processed: $records_processed,
                    error_message: $error_message
                })
                CREATE (r)-[:RUN_OF]->(j)
            """, 
                job_name=job_name,
                run_id=event.get('run_id'),
                status=event.get('status'),
                timestamp=event.get('timestamp'),
                duration_seconds=event.get('duration_seconds'),
                records_processed=event.get('records_processed'),
                error_message=event.get('error_message', '')
            )

            # Handle writes (outputs)
            for table in event.get('writes', []):
                session.run("""
                    MERGE (t:Table {name: $table_name})
                    MATCH (j:Job {name: $job_name})
                    MERGE (j)-[:WRITES_TO]->(t)
                """, table_name=table, job_name=job_name)

            # Handle reads (inputs)
            for table in event.get('reads', []):
                session.run("""
                    MERGE (t:Table {name: $table_name})
                    MATCH (j:Job {name: $job_name})
                    MERGE (j)-[:READS_FROM]->(t)
                """, table_name=table, job_name=job_name)

    def process_schema_change(self, event):
        """Process a schema_change event and update Neo4j + Chroma."""
        table_name = event.get('table_name')
        col_name = event.get('column_name')
        change_type = event.get('change_type')
        col_type = event.get('column_type', 'UNKNOWN')
        desc = event.get('description', '')
        
        with self.neo4j_driver.session() as session:
            # Ensure table exists
            session.run("MERGE (t:Table {name: $table_name})", table_name=table_name)
            
            if change_type == 'column_added' or change_type == 'column_modified':
                session.run("""
                    MATCH (t:Table {name: $table_name})
                    MERGE (c:Column {column_name: $col_name, table_name: $table_name})
                    SET c.data_type = $col_type, c.description = $desc
                    MERGE (t)-[:HAS_COLUMN]->(c)
                """, table_name=table_name, col_name=col_name, col_type=col_type, desc=desc)
                
                # Update Chroma embeddings
                if desc:
                    embedding = self.encoder.encode(desc).tolist()
                    doc_id = f"column_{table_name}_{col_name}"
                    metadata = {"type": "column", "table_name": table_name, "column_name": col_name}
                    
                    self.collection.upsert(
                        ids=[doc_id],
                        embeddings=[embedding],
                        documents=[desc],
                        metadatas=[metadata]
                    )
            elif change_type == 'column_removed':
                session.run("""
                    MATCH (t:Table {name: $table_name})-[:HAS_COLUMN]->(c:Column {column_name: $col_name, table_name: $table_name})
                    DETACH DELETE c
                """, table_name=table_name, col_name=col_name)
                
                # Remove from Chroma
                doc_id = f"column_{table_name}_{col_name}"
                try:
                    self.collection.delete(ids=[doc_id])
                except Exception:
                    pass

    def run(self):
        """Main consumer loop."""
        logger.info("Waiting for events... Press Ctrl+C to stop.")
        try:
            for message in self.consumer:
                event = message.value
                event_type = event.get('event_type')
                
                # Track latency
                event_time_str = event.get('timestamp')
                latency_ms = 0
                if event_time_str:
                    try:
                        # Assuming ISO format Z or offset
                        if event_time_str.endswith('Z'):
                            event_time_str = event_time_str[:-1] + '+00:00'
                        event_time = datetime.fromisoformat(event_time_str)
                        # Naive to aware if needed or just use timestamp
                        now = datetime.now(event_time.tzinfo)
                        latency_ms = (now - event_time).total_seconds() * 1000
                    except Exception:
                        pass

                start_process_time = time.time()
                
                if event_type == 'job_run':
                    self.process_job_run(event)
                    process_time = (time.time() - start_process_time) * 1000
                    logger.info(f"Processed JobRun: {event.get('job_name')} [{event.get('status')}] - Latency: {latency_ms:.2f}ms, ProcessTime: {process_time:.2f}ms")
                elif event_type == 'schema_change':
                    self.process_schema_change(event)
                    process_time = (time.time() - start_process_time) * 1000
                    logger.info(f"Processed SchemaChange: {event.get('table_name')}.{event.get('column_name')} [{event.get('change_type')}] - Latency: {latency_ms:.2f}ms, ProcessTime: {process_time:.2f}ms")
                else:
                    logger.warning(f"Unknown event type: {event_type}")
                    
        except KeyboardInterrupt:
            logger.info("Shutting down consumer...")
        finally:
            self.consumer.close()
            self.neo4j_driver.close()
            logger.info("Resources cleaned up.")


if __name__ == "__main__":
    consumer = LineageEventConsumer()
    consumer.run()
