"""
Agent Orchestrator
==================

The main entry point for answering user questions.
Routes the question, executes the chosen strategy (cypher, vector, or hybrid),
and synthesizes a final answer.
"""

import sys
import os
from typing import Dict, Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import OLLAMA_BASE_URL, OLLAMA_MODEL
from langchain_ollama import ChatOllama
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser

from rag.cypher_chain import query_graph
from rag.vector_search import search_and_answer, search_similar
from rag.router import classify_question

llm = ChatOllama(model=OLLAMA_MODEL, base_url=OLLAMA_BASE_URL, temperature=0)

HYBRID_SYNTHESIS_PROMPT = """
You are a senior data architect assistant.
You must synthesize a clear, comprehensive answer using the provided contexts.
Combine both structural knowledge (from the graph) and semantic knowledge (from the vector DB).

# User Question:
{question}

# Graph Database Results (Structural/Lineage):
{graph_context}

# Vector Database Results (Semantic/Descriptions):
{vector_context}

Answer:
"""

hybrid_template = PromptTemplate(
    input_variables=["question", "graph_context", "vector_context"],
    template=HYBRID_SYNTHESIS_PROMPT
)
hybrid_chain = hybrid_template | llm | StrOutputParser()


def ask(question: str) -> Dict[str, Any]:
    """
    Main function to answer a question using the RAG/Agent system.
    """
    route = classify_question(question)
    
    result = {
        "question": question,
        "route": route,
        "cypher_result": None,
        "vector_result": None,
        "answer": "",
        "sources": []
    }
    
    if route == "cypher":
        graph_res = query_graph(question)
        result["cypher_result"] = graph_res
        result["answer"] = graph_res.get("answer", "Error getting answer.")
        result["sources"] = ["Neo4j Graph Database"]
        if graph_res.get("cypher"):
            result["sources"].append(f"Cypher used: {graph_res['cypher']}")
            
    elif route == "vector":
        vec_res = search_and_answer(question)
        result["vector_result"] = vec_res
        result["answer"] = vec_res.get("answer", "Error getting answer.")
        docs = vec_res.get("retrieved_docs", [])
        for doc in docs:
            meta = doc.get("metadata", {})
            if meta.get("type") == "table":
                name = meta.get("table_name", "Unknown table")
            else:
                name = f"{meta.get('table_name', '?')}.{meta.get('column_name', '?')}"
            result["sources"].append(f"Document: {name}")
            
    elif route == "hybrid":
        # Run both
        graph_res = query_graph(question)
        vec_docs = search_similar(question, n_results=3)
        
        result["cypher_result"] = graph_res
        result["vector_result"] = {"retrieved_docs": vec_docs}
        
        # Synthesize combined answer
        vector_context = "\n\n".join([d['content'] for d in vec_docs])
        graph_context = str(graph_res.get("raw_results", "No structural results found."))
        
        combined_answer = hybrid_chain.invoke({
            "question": question,
            "graph_context": graph_context,
            "vector_context": vector_context
        })
        
        result["answer"] = combined_answer
        result["sources"] = ["Neo4j Graph Database", "Chroma Vector Database"]
        if graph_res.get("cypher"):
            result["sources"].append(f"Cypher used: {graph_res['cypher']}")
            
    return result

if __name__ == '__main__':
    print("Welcome to LineageIQ Agent. Type 'quit' to exit.")
    while True:
        try:
            q = input("\nAsk a question: ")
            if q.lower().strip() in ['quit', 'exit', 'q']:
                break
            
            print("Thinking...")
            res = ask(q)
            print(f"\n--- Route chosen: {res['route'].upper()} ---")
            print(f"Answer:\n{res['answer']}\n")
            print("Sources:")
            for s in res['sources']:
                print(f" - {s}")
        except KeyboardInterrupt:
            break
