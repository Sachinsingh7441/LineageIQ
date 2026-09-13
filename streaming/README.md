# 📡 Streaming Module — Kafka Real-Time Ingestion

## Overview

This module adds a **real-time streaming layer** to the LineageIQ system. Instead of loading data once with scripts, events flow continuously through Kafka — just like in a production data platform.

| Component | Purpose |
|---|---|
| `event_producer.py` | Simulates a pipeline orchestrator emitting events |
| `event_consumer.py` | Consumes events and updates Neo4j + Chroma in real-time |

---

## Technologies Used

### Apache Kafka (Event Streaming Platform)

**What it is**: Kafka is a **distributed event streaming platform**. Think of it as a highly reliable, high-throughput message queue. Producers publish messages (events) to **topics**, and consumers read from those topics.

**Core concepts**:

| Concept | Explanation |
|---|---|
| **Topic** | A named channel for events (like a mailbox). We use `lineage-events`. |
| **Producer** | A program that publishes events to a topic. |
| **Consumer** | A program that reads events from a topic. |
| **Broker** | The Kafka server that stores and serves events. |
| **Consumer Group** | A group of consumers that share the work of reading a topic. Each event is processed by exactly one consumer in the group. |
| **Offset** | The position of a consumer in the topic — "I've read up to message #42." |

**How Kafka works (simplified)**:
```
Producer writes event → Kafka Broker stores it → Consumer reads and processes it
                              ↕
                    Events are persisted on disk
                    (can be replayed if needed)
```

**Why Kafka is important**: It's the industry standard for event streaming. LinkedIn, Netflix, Uber, and most major tech companies use it. Adding Kafka to your project demonstrates real streaming competence.

### Redpanda (Kafka-Compatible Alternative)

**What it is**: Redpanda is a **Kafka-compatible** streaming platform that's much easier to run locally. It speaks the same protocol as Kafka (so our Python code doesn't change), but:
- **Simpler to set up**: Single binary, no JVM, no ZooKeeper
- **Lower resource usage**: Uses less RAM and CPU than Kafka
- **Same API**: Any Kafka client library works with Redpanda

We use Redpanda in our `docker-compose.yml` for local development. In production, you could swap in real Kafka without changing any code.

### kafka-python-ng (Python Kafka Client)

**What it is**: A Python library that implements the Kafka protocol. The `-ng` version is the actively maintained fork of the original `kafka-python` library.

**Key classes**:
```python
from kafka import KafkaProducer, KafkaConsumer

# Producer: sends events
producer = KafkaProducer(
    bootstrap_servers='localhost:9092',
    value_serializer=lambda v: json.dumps(v).encode('utf-8')
)
producer.send('lineage-events', {"event": "data"})

# Consumer: reads events
consumer = KafkaConsumer(
    'lineage-events',
    bootstrap_servers='localhost:9092',
    value_deserializer=lambda m: json.loads(m.decode('utf-8'))
)
for message in consumer:
    process(message.value)
```

---

## Event Types

### 1. Job Run Events (90% of events)

Emitted when an ETL pipeline executes:

```json
{
    "event_type": "job_run",
    "job_name": "build_curated_orders",
    "reads": ["stg_orders", "stg_payments", "stg_shipping"],
    "writes": ["curated_orders"],
    "status": "success",
    "records_processed": 12450,
    "duration_seconds": 145,
    "timestamp": "2026-09-13T12:00:00+00:00",
    "run_id": "build_curated_orders_20260913120000_42"
}
```

Failed runs include an error message:
```json
{
    "event_type": "job_run",
    "status": "failed",
    "error_message": "Connection timeout to source database after 30s",
    ...
}
```

### 2. Schema Change Events (10% of events)

Emitted when a table's schema is modified:

```json
{
    "event_type": "schema_change",
    "table_name": "raw_orders",
    "change_type": "column_added",
    "column_name": "promo_code",
    "column_type": "STRING",
    "description": "Promotional code applied to the order",
    "timestamp": "2026-09-13T12:05:00+00:00"
}
```

Change types: `column_added`, `column_removed`, `column_modified`

---

## Component Details

### `event_producer.py` — Kafka Event Producer

**Purpose**: Simulates a pipeline orchestrator (like Apache Airflow or Dagster) continuously emitting lineage events.

**How it works**:
1. Connects to Kafka broker
2. In a loop, generates random events using actual job/table names from the data generator
3. Sends each event to the `lineage-events` topic
4. Prints a summary of each emitted event

**Usage**:
```bash
# Default: emit events every 5 seconds, run forever
python streaming/event_producer.py

# Custom interval (2 seconds between events)
python streaming/event_producer.py --interval 2

# Emit exactly 20 events then stop
python streaming/event_producer.py --num-events 20

# Fast burst for testing
python streaming/event_producer.py --interval 0.5 --num-events 100
```

**Graceful shutdown**: Press `Ctrl+C` to stop. The producer flushes any pending messages before closing.

---

### `event_consumer.py` — Kafka Event Consumer

**Purpose**: Reads events from Kafka and updates both Neo4j and Chroma in real-time — keeping the lineage graph and vector database synchronized with the latest pipeline activity.

**How it processes each event type**:

#### Job Run Events:
1. **MERGE** the Job node (create if it doesn't exist)
2. **CREATE** a new JobRun node with all execution metadata
3. **CREATE** a `RUN_OF` relationship connecting the run to its job
4. **MERGE** any new tables referenced in `reads`/`writes`
5. **MERGE** `READS_FROM` and `WRITES_TO` relationships

#### Schema Change Events:
1. `column_added`: Creates a new Column node + `HAS_COLUMN` relationship, re-embeds the description into Chroma
2. `column_removed`: Deletes the Column node and removes its embedding from Chroma
3. `column_modified`: Updates the Column node properties and re-embeds

**Latency tracking**: For each event, the consumer logs:
- **Event latency**: Time from event timestamp to processing start
- **Processing time**: Time to update Neo4j + Chroma

**Usage**:
```bash
python streaming/event_consumer.py
```

**Output example**:
```
2026-09-13 12:00:05 - INFO - Processed JobRun: build_curated_orders [success] - Latency: 5230.00ms, ProcessTime: 45.20ms
2026-09-13 12:00:10 - INFO - Processed SchemaChange: raw_orders.promo_code [column_added] - Latency: 3120.00ms, ProcessTime: 125.80ms
```

---

## Setting Up Kafka (Redpanda)

### Step 1: Enable Redpanda in Docker Compose
Edit `docker-compose.yml` and **uncomment** the Redpanda and Redpanda Console sections.

### Step 2: Start the Services
```bash
docker-compose up -d
```

### Step 3: Verify Kafka is Running
- **Redpanda Console** (web UI): [http://localhost:8080](http://localhost:8080)
- **Kafka API**: Port 9092

### Step 4: Run Consumer and Producer
```bash
# Terminal 1: Start consumer (waits for events)
python streaming/event_consumer.py

# Terminal 2: Start producer (emits events)
python streaming/event_producer.py --interval 5
```

### Step 5: Watch the Graph Update
Open Neo4j Browser at [http://localhost:7474](http://localhost:7474) and run:
```cypher
MATCH (jr:JobRun)-[:RUN_OF]->(j:Job) RETURN jr, j LIMIT 10
```
You'll see new JobRun nodes appearing as the consumer processes events!

---

## Concepts Explained

### Event-Driven Architecture
Instead of periodically polling for changes (batch), an event-driven system **reacts to events as they happen**. Benefits:
- **Lower latency**: Updates happen in seconds, not hours
- **Decoupling**: Producer and consumer don't know about each other
- **Replayability**: Events are stored in Kafka and can be replayed

### Near-Real-Time Processing
"Near-real-time" means there's a small delay (milliseconds to seconds) between an event occurring and the system reacting. This is the standard for most data engineering use cases — true real-time (zero delay) is only needed for things like stock trading.

### Change Data Capture (CDC)
CDC is the pattern of capturing changes to a database and emitting them as events. In production, tools like **Debezium** do this automatically. Our producer simulates this by generating synthetic events.

---

## Prerequisites

- **Docker** with Redpanda section uncommented in `docker-compose.yml`
- **Neo4j** running with data loaded
- **Chroma** populated with embeddings
- **Python packages**: `kafka-python-ng`, `neo4j`, `chromadb`, `sentence-transformers`
