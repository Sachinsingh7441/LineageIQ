"""
Embed table and column metadata into Chroma vector database.

This script reads JSON metadata from the data/synthetic/ directory,
creates rich text representations, generates embeddings, and stores
them in Chroma to enable semantic search capabilities.
"""

import sys
import os
import json

# Import shared configuration
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import CHROMA_PERSIST_DIR, CHROMA_COLLECTION_NAME, EMBEDDING_MODEL_NAME, DATA_DIR

try:
    import chromadb
    from sentence_transformers import SentenceTransformer
except ImportError:
    print("Error: Required libraries not found.")
    print("Please install them using 'pip install chromadb sentence-transformers'.")
    sys.exit(1)


# Initialize global model and client to be reused
print(f"Loading embedding model '{EMBEDDING_MODEL_NAME}' (this may take a moment)...")
model = SentenceTransformer(EMBEDDING_MODEL_NAME)

print(f"Initializing Chroma persistent client at '{CHROMA_PERSIST_DIR}'...")
chroma_client = chromadb.PersistentClient(path=CHROMA_PERSIST_DIR)
collection = chroma_client.get_or_create_collection(name=CHROMA_COLLECTION_NAME)


def load_json(filename):
    """Utility to load a JSON file from the synthetic data directory."""
    filepath = os.path.join(DATA_DIR, filename)
    if not os.path.exists(filepath):
        print(f"Warning: File {filepath} not found.")
        return []
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def embed_tables(tables):
    """Generate embeddings for tables and upsert them into Chroma."""
    if not tables:
        return
        
    print(f"Embedding {len(tables)} tables...")
    ids = []
    documents = []
    metadatas = []
    
    for t in tables:
        # Create a rich text document for better semantic matching
        doc = f"Table: {t['name']}\nLayer: {t['layer']}\nDescription: {t['description']}"
        
        ids.append(f"table_{t['name']}")
        documents.append(doc)
        metadatas.append({
            "type": "table",
            "table_name": t["name"],
            "layer": t["layer"],
        })
        
    # Generate embeddings
    embeddings = model.encode(documents).tolist()
    
    # Upsert to Chroma
    collection.upsert(
        ids=ids,
        embeddings=embeddings,
        documents=documents,
        metadatas=metadatas
    )
    print(f"Successfully upserted {len(tables)} table embeddings.")


def embed_columns(columns):
    """Generate embeddings for columns and upsert them into Chroma."""
    if not columns:
        return
        
    print(f"Embedding {len(columns)} columns...")
    ids = []
    documents = []
    metadatas = []
    
    for c in columns:
        # Create a rich text document for the column
        doc = f"Column: {c['column_name']} (in Table: {c['table_name']})\nType: {c['data_type']}\nDescription: {c['description']}"
        
        # Unique ID for the column across the entire database
        ids.append(f"column_{c['table_name']}_{c['column_name']}")
        documents.append(doc)
        metadatas.append({
            "type": "column",
            "table_name": c["table_name"],
            "column_name": c["column_name"],
            "data_type": c["data_type"],
        })
        
    # Process in batches to avoid memory issues with many columns
    batch_size = 100
    for i in range(0, len(documents), batch_size):
        batch_docs = documents[i:i+batch_size]
        batch_embeddings = model.encode(batch_docs).tolist()
        
        collection.upsert(
            ids=ids[i:i+batch_size],
            embeddings=batch_embeddings,
            documents=batch_docs,
            metadatas=metadatas[i:i+batch_size]
        )
    print(f"Successfully upserted {len(columns)} column embeddings.")


def search_similar(query_text, n_results=5):
    """
    Search for similar tables or columns in the Chroma vector database.
    This function can be imported and used by other modules.
    
    Args:
        query_text (str): The search query.
        n_results (int): Number of top results to return.
        
    Returns:
        dict: The Chroma search results including documents and metadata.
    """
    query_embedding = model.encode([query_text]).tolist()
    
    results = collection.query(
        query_embeddings=query_embedding,
        n_results=n_results
    )
    
    return results


def main():
    """Main execution block to load data and populate the vector DB."""
    tables = load_json("tables.json")
    columns = load_json("columns.json")
    
    if not tables and not columns:
        print("No data found to embed. Please run data_generator.py first.")
        sys.exit(1)
        
    embed_tables(tables)
    embed_columns(columns)
    
    print("\nVector database population complete.")
    
    # Test the vector DB with a sample query
    test_query = "payment refunds"
    print(f"\n--- Testing similarity search for: '{test_query}' ---")
    
    results = search_similar(test_query, n_results=3)
    
    if results and results["documents"] and results["documents"][0]:
        for i, (doc, meta, dist) in enumerate(zip(
            results["documents"][0], 
            results["metadatas"][0],
            results["distances"][0] if "distances" in results else [0]*len(results["documents"][0])
        )):
            item_type = meta.get("type", "unknown")
            name = meta.get("table_name") if item_type == "table" else f"{meta.get('table_name')}.{meta.get('column_name')}"
            print(f"\nResult {i+1} ({item_type}: {name}) - Distance: {dist:.4f}")
            # Print first 100 characters of the document
            print(f"Content: {doc[:100]}...")
    else:
        print("No results found.")
    print("--------------------------------------------------\n")


if __name__ == "__main__":
    main()
