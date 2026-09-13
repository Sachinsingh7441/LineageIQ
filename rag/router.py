"""
Question Router
===============

Routes incoming user questions to the appropriate search strategy:
'cypher' (structural), 'vector' (semantic), or 'hybrid' (both).
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import OLLAMA_BASE_URL, OLLAMA_MODEL
from langchain_ollama import ChatOllama
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser

llm = ChatOllama(model=OLLAMA_MODEL, base_url=OLLAMA_BASE_URL, temperature=0)

ROUTER_PROMPT = """
You are a specialized routing assistant for a data lineage system.
Given a user's question, you must classify it into exactly one of three categories: 'cypher', 'vector', or 'hybrid'.

# Categories:
- cypher: The question is structural or about relationships (lineage, upstream dependencies, downstream impact, column schemas, job execution, failures).
- vector: The question is semantic, descriptive, or asks about meaning (what tables relate to a concept, finding tables by topic, looking for specific types of data).
- hybrid: The question requires both structural lineage knowledge and semantic conceptual search.

# Examples:
Question: what feeds into curated_orders?
Category: cypher

Question: what tables does build_curated_orders read?
Category: cypher

Question: show me the upstream dependencies of rpt_daily_sales
Category: cypher

Question: did any jobs fail yesterday?
Category: cypher

Question: which tables relate to customer refunds?
Category: vector

Question: find tables about shipping performance
Category: vector

Question: what data do we have about payment methods?
Category: vector

Question: explain the lineage of the daily sales report and what data it contains
Category: hybrid

Question: what customer-related tables feed into the revenue report?
Category: hybrid

Respond ONLY with the category name (cypher, vector, or hybrid). Do not include any other text.

Question: {question}
Category:
"""

router_template = PromptTemplate(
    input_variables=["question"],
    template=ROUTER_PROMPT
)

router_chain = router_template | llm | StrOutputParser()

def classify_question(question: str) -> str:
    """
    Uses the LLM to classify the question. Falls back to keyword logic if classification fails.
    """
    try:
        category = router_chain.invoke({"question": question}).strip().lower()
        if category in ["cypher", "vector", "hybrid"]:
            return category
    except Exception as e:
        print(f"Warning: Router LLM failed, using fallback. Error: {e}")
        
    # Keyword fallback
    q_lower = question.lower()
    cypher_keywords = ["feed", "depend", "upstream", "downstream", "job", "fail", "column", "read", "write", "lineage"]
    vector_keywords = ["about", "relate", "find", "search", "concept", "meaning"]
    
    has_cypher = any(k in q_lower for k in cypher_keywords)
    has_vector = any(k in q_lower for k in vector_keywords)
    
    if has_cypher and has_vector:
        return "hybrid"
    elif has_vector:
        return "vector"
    else:
        return "cypher"

if __name__ == '__main__':
    print("Testing Router...")
    test_questions = [
        "did any jobs fail yesterday?",
        "which tables relate to customer refunds?",
        "what customer-related tables feed into the revenue report?"
    ]
    for q in test_questions:
        print(f"Q: {q}")
        print(f"Route: {classify_question(q)}\n")
