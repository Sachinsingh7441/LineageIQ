"""
Load synthetic lineage data into Neo4j graph database.

This script reads JSON files from the data/synthetic/ directory and creates
nodes and relationships in Neo4j to represent the data warehouse lineage.
"""

import sys
import os
import json
import argparse

# Import shared configuration
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD, DATA_DIR

try:
    from neo4j import GraphDatabase
except ImportError:
    print("Error: neo4j library not found. Please install it using 'pip install neo4j'.")
    sys.exit(1)


def load_json(filename):
    """Utility to load a JSON file from the synthetic data directory."""
    filepath = os.path.join(DATA_DIR, filename)
    if not os.path.exists(filepath):
        print(f"Warning: File {filepath} not found.")
        return []
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def clear_database(driver):
    """Deletes all nodes and relationships in the database."""
    print("Clearing existing graph database...")
    with driver.session() as session:
        session.run("MATCH (n) DETACH DELETE n")
    print("Database cleared.")


def load_tables(driver, tables):
    """Loads Table nodes into Neo4j."""
    print(f"Loading {len(tables)} tables...")
    query = """
    UNWIND $tables AS t
    MERGE (n:Table {name: t.name})
    SET n.layer = t.layer,
        n.description = t.description,
        n.column_count = t.column_count
    """
    with driver.session() as session:
        session.run(query, tables=tables)


def load_columns(driver, columns):
    """Loads Column nodes and links them to Tables."""
    print(f"Loading {len(columns)} columns...")
    query = """
    UNWIND $columns AS c
    MERGE (t:Table {name: c.table_name})
    MERGE (col:Column {column_name: c.column_name, table_name: c.table_name})
    SET col.data_type = c.data_type,
        col.description = c.description
    MERGE (t)-[:HAS_COLUMN]->(col)
    """
    with driver.session() as session:
        session.run(query, columns=columns)


def load_jobs(driver, jobs):
    """Loads Job nodes into Neo4j."""
    print(f"Loading {len(jobs)} jobs...")
    query = """
    UNWIND $jobs AS j
    MERGE (n:Job {name: j.name})
    SET n.description = j.description,
        n.schedule = j.schedule,
        n.owner = j.owner
    """
    with driver.session() as session:
        session.run(query, jobs=jobs)


def load_lineage_edges(driver, edges):
    """Loads READS_FROM and WRITES_TO relationships."""
    print(f"Loading {len(edges)} lineage edges...")
    
    reads_edges = [e for e in edges if e["direction"] == "reads"]
    writes_edges = [e for e in edges if e["direction"] == "writes"]
    
    reads_query = """
    UNWIND $edges AS e
    MERGE (j:Job {name: e.job_name})
    MERGE (t:Table {name: e.source_table})
    MERGE (j)-[:READS_FROM]->(t)
    """
    
    writes_query = """
    UNWIND $edges AS e
    MERGE (j:Job {name: e.job_name})
    MERGE (t:Table {name: e.target_table})
    MERGE (j)-[:WRITES_TO]->(t)
    """
    
    with driver.session() as session:
        if reads_edges:
            session.run(reads_query, edges=reads_edges)
        if writes_edges:
            session.run(writes_query, edges=writes_edges)


def build_table_dependencies(driver):
    """Infers and creates DEPENDS_ON relationships between tables."""
    print("Building table dependencies (DEPENDS_ON)...")
    query = """
    MATCH (source:Table)<-[:READS_FROM]-(j:Job)-[:WRITES_TO]->(target:Table)
    MERGE (target)-[:DEPENDS_ON]->(source)
    """
    with driver.session() as session:
        session.run(query)


def load_job_runs(driver, runs):
    """Loads JobRun nodes and links them to Jobs."""
    print(f"Loading {len(runs)} job runs...")
    query = """
    UNWIND $runs AS r
    MERGE (j:Job {name: r.job_name})
    MERGE (run:JobRun {run_id: r.run_id})
    SET run.started_at = r.started_at,
        run.duration_seconds = r.duration_seconds,
        run.status = r.status,
        run.error_message = r.error_message,
        run.records_processed = r.records_processed
    MERGE (run)-[:RUN_OF]->(j)
    """
    with driver.session() as session:
        session.run(query, runs=runs)


def verify_graph(driver):
    """Runs basic verification queries to print the graph summary."""
    print("\n--- Graph Verification Summary ---")
    queries = {
        "Tables": "MATCH (n:Table) RETURN count(n) AS count",
        "Columns": "MATCH (n:Column) RETURN count(n) AS count",
        "Jobs": "MATCH (n:Job) RETURN count(n) AS count",
        "Job Runs": "MATCH (n:JobRun) RETURN count(n) AS count",
        "HAS_COLUMN rels": "MATCH ()-[r:HAS_COLUMN]->() RETURN count(r) AS count",
        "READS_FROM rels": "MATCH ()-[r:READS_FROM]->() RETURN count(r) AS count",
        "WRITES_TO rels": "MATCH ()-[r:WRITES_TO]->() RETURN count(r) AS count",
        "DEPENDS_ON rels": "MATCH ()-[r:DEPENDS_ON]->() RETURN count(r) AS count",
        "RUN_OF rels": "MATCH ()-[r:RUN_OF]->() RETURN count(r) AS count",
    }
    
    with driver.session() as session:
        for name, query in queries.items():
            result = session.run(query).single()
            print(f"{name}: {result['count']}")
    print("----------------------------------\n")


def main():
    parser = argparse.ArgumentParser(description="Load lineage data into Neo4j.")
    parser.add_argument("--clear", action="store_true", help="Clear the database before loading")
    args = parser.parse_args()

    print(f"Connecting to Neo4j at {NEO4J_URI}...")
    try:
        driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
        driver.verify_connectivity()
    except Exception as e:
        print(f"Failed to connect to Neo4j: {e}")
        sys.exit(1)

    if args.clear:
        clear_database(driver)

    tables = load_json("tables.json")
    columns = load_json("columns.json")
    jobs = load_json("jobs.json")
    edges = load_json("lineage_edges.json")
    runs = load_json("job_runs.json")

    if tables:
        load_tables(driver, tables)
    if columns:
        load_columns(driver, columns)
    if jobs:
        load_jobs(driver, jobs)
    if edges:
        load_lineage_edges(driver, edges)
        build_table_dependencies(driver)
    if runs:
        load_job_runs(driver, runs)

    verify_graph(driver)
    
    driver.close()
    print("Graph loading complete.")


if __name__ == "__main__":
    main()
