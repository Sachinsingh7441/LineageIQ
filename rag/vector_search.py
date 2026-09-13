"""
Vector Search
=============

Uses Chroma DB and sentence-transformers to find semantically similar documents
and ChatOllama to synthesize answers.
"""

import sys
import os
from typing import Dict, Any, List

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import (
    CHROMA_PERSIST_DIR,
    CHROMA_COLLECTION_NAME,
    EMBEDDING_MODEL_NAME,
    OLLAMA_BASE_URL,
    OLLAMA_MODEL,
)

import chromadb
from chromadb.utils import embedding_functions
from langchain_ollama import ChatOllama
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser

# Initialize ChromaDB Client
try:
    chroma_client = chromadb.PersistentClient(path=CHROMA_PERSIST_DIR)
    embed_fn = embedding_functions.SentenceTransformerEmbeddingFunction(model_name=EMBEDDING_MODEL_NAME)
    collection = chroma_client.get_or_create_collection(
        name=CHROMA_COLLECTION_NAME,
        embedding_function=embed_fn
    )
except Exception as e:
    print(f"Warning: Could not initialize Chroma DB: {e}")
    collection = None

# Initialize LLM
llm = ChatOllama(model=OLLAMA_MODEL, base_url=OLLAMA_BASE_URL, temperature=0)

SYNTHESIS_PROMPT = """
You are a helpful data assistant.
Use the following retrieved documents to answer the user's question.
If the answer is not contained in the documents, say "I don't know based on the provided context."

# Retrieved Documents:
{context}

# Question:
{question}

Answer:
"""

synthesis_template = PromptTemplate(
    input_variables=["context", "question"],
    template=SYNTHESIS_PROMPT
)
synthesis_chain = synthesis_template | llm | StrOutputParser()

def search_similar(query: str, n_results: int = 5) -> List[Dict[str, Any]]:
    """
    Embeds the query and searches Chroma for similar documents without using an LLM.
    """
    if not collection:
        return []
    
    try:
        results = collection.query(
            query_texts=[query],
            n_results=n_results
        )
        
        docs = []
        if results and results.get("documents") and len(results["documents"]) > 0:
            for i in range(len(results["documents"][0])):
                docs.append({
                    "content": results["documents"][0][i],
                    "metadata": results["metadatas"][0][i] if results.get("metadatas") else {}
                })
        return docs
    except Exception as e:
        print(f"Error querying Chroma: {e}")
        return []

def search_and_answer(question: str, n_results: int = 5) -> Dict[str, Any]:
    """
    Queries Chroma for similar documents and passes them to the LLM to synthesize an answer.
    """
    retrieved_docs = search_similar(question, n_results)
    
    if not retrieved_docs:
        return {
            "question": question,
            "retrieved_docs": [],
            "answer": "I couldn't find any relevant documents to answer your question."
        }
        
    context = "\n\n".join([f"Document {i+1}:\n{doc['content']}" for i, doc in enumerate(retrieved_docs)])
    
    answer = synthesis_chain.invoke({"context": context, "question": question})
    
    return {
        "question": question,
        "retrieved_docs": retrieved_docs,
        "answer": answer
    }

if __name__ == '__main__':
    print("Testing Vector Search...")
    q = "what data do we have about payment methods?"
    print(f"\nQ: {q}")
    res = search_and_answer(q)
    print(f"Retrieved {len(res['retrieved_docs'])} docs")
    print(f"Answer: {res['answer']}")
