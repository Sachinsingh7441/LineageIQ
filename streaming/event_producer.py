"""
Kafka Event Producer for LineageIQ
========================================

Simulates a pipeline orchestrator (like Airflow or Dagster) emitting 
lineage and job execution events to Kafka.

This script acts as a mock event generator to populate the Kafka topic
with realistic pipeline execution events and schema change events.

Usage:
  python event_producer.py [--interval 5] [--num-events 0]
"""

import sys
import os
import time
import json
import random
import argparse
from datetime import datetime, timezone

# Add parent directory to path to import config and scripts
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import KAFKA_BOOTSTRAP_SERVERS, KAFKA_TOPIC
from scripts.data_generator import JOBS, TABLES

try:
    from kafka import KafkaProducer
except ImportError:
    print("Error: kafka-python-ng is not installed.")
    print("Run: pip install kafka-python-ng")
    sys.exit(1)


def create_producer():
    """Create and return a KafkaProducer instance."""
    try:
        producer = KafkaProducer(
            bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
            value_serializer=lambda v: json.dumps(v).encode('utf-8')
        )
        print(f"Connected to Kafka broker at {KAFKA_BOOTSTRAP_SERVERS}")
        return producer
    except Exception as e:
        print(f"Failed to connect to Kafka: {e}")
        sys.exit(1)


def generate_job_run_event():
    """Generate a synthetic job run event."""
    job = random.choice(JOBS)
    now = datetime.now(timezone.utc)
    
    # 90% success, 10% failure
    is_success = random.random() < 0.9
    status = "success" if is_success else "failed"
    
    # Generate run ID based on time
    run_id = f"{job['name']}_{now.strftime('%Y%m%d%H%M%S')}_{random.randint(0, 100)}"
    
    event = {
        "event_type": "job_run",
        "job_name": job["name"],
        "reads": job.get("reads", []),
        "writes": job.get("writes", []),
        "status": status,
        "records_processed": random.randint(100, 50000) if is_success else 0,
        "duration_seconds": random.randint(10, 600),
        "timestamp": now.isoformat(),
        "run_id": run_id
    }
    
    if not is_success:
        event["error_message"] = "Random failure generated for testing."
        
    return event


def generate_schema_change_event():
    """Generate a synthetic schema change event."""
    table = random.choice(TABLES)
    now = datetime.now(timezone.utc)
    
    change_type = random.choice(["column_added", "column_removed", "column_modified"])
    col_name = f"test_col_{random.randint(1, 100)}"
    
    event = {
        "event_type": "schema_change",
        "table_name": table["name"],
        "change_type": change_type,
        "column_name": col_name,
        "timestamp": now.isoformat()
    }
    
    if change_type in ["column_added", "column_modified"]:
        event["column_type"] = random.choice(["STRING", "INTEGER", "BOOLEAN", "TIMESTAMP"])
        event["description"] = f"Auto-generated column for testing {change_type}"
        
    return event


def main():
    """Main execution loop for event generation."""
    parser = argparse.ArgumentParser(description="Kafka Event Producer for LineageIQ")
    parser.add_argument("--interval", type=float, default=5.0, help="Seconds between events")
    parser.add_argument("--num-events", type=int, default=0, help="Total events to emit (0=infinite)")
    args = parser.parse_args()
    
    producer = create_producer()
    print(f"Starting to emit events to topic '{KAFKA_TOPIC}' every {args.interval} seconds...")
    print("Press Ctrl+C to stop.")
    
    count = 0
    try:
        while True:
            # 90% job runs, 10% schema changes
            if random.random() < 0.9:
                event = generate_job_run_event()
                summary = f"JobRun: {event['job_name']} ({event['status']})"
            else:
                event = generate_schema_change_event()
                summary = f"SchemaChange: {event['table_name']} ({event['change_type']} {event['column_name']})"
                
            producer.send(KAFKA_TOPIC, event)
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Emitted: {summary}")
            
            count += 1
            if args.num_events > 0 and count >= args.num_events:
                print(f"Reached target of {args.num_events} events. Stopping.")
                break
                
            time.sleep(args.interval)
            
    except KeyboardInterrupt:
        print("\nStopping event producer...")
    finally:
        producer.flush()
        producer.close()
        print("Producer closed.")


if __name__ == "__main__":
    main()
