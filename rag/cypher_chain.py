"""
Cypher Chain for Text-to-Cypher Translation
===========================================

Uses LangChain and Ollama to translate natural language questions into Neo4j Cypher queries.
It uses the Neo4jGraph to execute the queries and returns the results.
"""

import sys
import os
import json
from typing import Dict, Any

# Insert the parent directory into sys.path to allow imports from config
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import (
    NEO4J_URI,
    NEO4J_USER,
    NEO4J_PASSWORD,
    OLLAMA_BASE_URL,
    OLLAMA_MODEL,
)

from langchain_ollama import ChatOllama
from langchain_community.graphs import Neo4jGraph
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser

# Initialize Graph
try:
    graph = Neo4jGraph(
        url=NEO4J_URI,
        username=NEO4J_USER,
        password=NEO4J_PASSWORD
    )
except Exception as e:
    print(f"Warning: Could not connect to Neo4j at {NEO4J_URI}: {e}")
    graph = None

# Initialize LLM
llm = ChatOllama(model=OLLAMA_MODEL, base_url=OLLAMA_BASE_URL, temperature=0)

CYPHER_PROMPT = """
You are an expert Neo4j Cypher developer for a data lineage system.
Convert the user's natural language question into a Cypher query based on the following graph schema.

# Schema
Node Types:
- Table: name, layer, description, column_count
- Column: column_name, data_type, description
- Job: name, description, schedule, owner
- JobRun: run_id, status, started_at, duration_seconds, error_message, records_processed

Relationship Types:
- (Table)-[:HAS_COLUMN]->(Column)
- (Job)-[:READS_FROM]->(Table)
- (Job)-[:WRITES_TO]->(Table)
- (Table)-[:DEPENDS_ON]->(Table)
- (JobRun)-[:RUN_OF]->(Job)

# Instructions:
- Only respond with the Cypher query. Do not include any explanations, markdown formatting, or apologies.
- Use the correct node labels and relationship types.

# Examples:
Question: what tables does build_curated_orders read?
Query: MATCH (j:Job {{name: 'build_curated_orders'}})-[:READS_FROM]->(t:Table) RETURN t.name

Question: show me the upstream dependencies of rpt_daily_sales
Query: MATCH (t:Table {{name: 'rpt_daily_sales'}})-[:DEPENDS_ON*1..]->(up:Table) RETURN DISTINCT up.name

Question: did any jobs fail yesterday?
Query: MATCH (jr:JobRun)-[:RUN_OF]->(j:Job) WHERE jr.status = 'failed' RETURN j.name, jr.error_message, jr.started_at LIMIT 10

Question: what columns does the curated_orders table have?
Query: MATCH (t:Table {{name: 'curated_orders'}})-[:HAS_COLUMN]->(c:Column) RETURN c.column_name, c.data_type

Question: what jobs write to the curated layer?
Query: MATCH (j:Job)-[:WRITES_TO]->(t:Table {{layer: 'curated'}}) RETURN DISTINCT j.name

# Question
Question: {question}
Query:
"""

cypher_prompt_template = PromptTemplate(
    input_variables=["question"],
    template=CYPHER_PROMPT
)

cypher_chain = cypher_prompt_template | llm | StrOutputParser()

ANSWER_PROMPT = """
You are an AI assistant answering questions about data lineage.
Given the original question, the Cypher query used, and the raw database results, formulate a natural language answer.

Question: {question}
Cypher Query: {cypher}
Raw Results: {results}

Answer:
"""

answer_prompt_template = PromptTemplate(
    input_variables=["question", "cypher", "results"],
    template=ANSWER_PROMPT
)

answer_chain = answer_prompt_template | llm | StrOutputParser()


def query_graph(question: str) -> Dict[str, Any]:
    """
    Translates a question to Cypher, executes it against Neo4j, and generates an answer.
    Catches syntax errors and retries once with feedback.
    """
    if not graph:
        return {"question": question, "error": "Neo4j connection not available"}

    cypher = ""
    raw_results = []
    
    try:
        # 1. Generate Cypher
        cypher = cypher_chain.invoke({"question": question}).strip()
        
        # 2. Execute against Neo4j
        raw_results = graph.query(cypher)
        
    except Exception as e:
        # Retry logic on syntax error
        error_msg = str(e)
        retry_prompt = PromptTemplate(
            input_variables=["question", "cypher", "error"],
            template="You previously generated this Cypher query for the question: \"{question}\"\nQuery: {cypher}\n\nIt resulted in this error: {error}\n\nPlease provide a corrected Cypher query. Only respond with the query."
        )
        retry_chain = retry_prompt | llm | StrOutputParser()
        
        try:
            cypher = retry_chain.invoke({"question": question, "cypher": cypher, "error": error_msg}).strip()
            raw_results = graph.query(cypher)
        except Exception as retry_e:
            return {
                "question": question,
                "cypher": cypher,
                "error": f"Failed after retry. Error: {str(retry_e)}",
                "raw_results": None,
                "answer": "I'm sorry, I couldn't generate a valid query for that question."
            }

    # 3. Generate Answer
    answer = answer_chain.invoke({
        "question": question,
        "cypher": cypher,
        "results": json.dumps(raw_results)
    })
    
    return {
        "question": question,
        "cypher": cypher,
        "raw_results": raw_results,
        "answer": answer
    }

if __name__ == '__main__':
    print("Testing Cypher Chain...")
    test_questions = [
        "what tables does build_curated_orders read?",
        "did any jobs fail recently?"
    ]
    for q in test_questions:
        print(f"\nQ: {q}")
        res = query_graph(q)
        print(f"Cypher: {res.get('cypher')}")
        print(f"Answer: {res.get('answer')}")
