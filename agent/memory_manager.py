# agent/memory_manager.py

import chromadb
from chromadb.utils import embedding_functions

# ---- Chroma Client Setup ----
chroma_client = chromadb.PersistentClient(path="./chroma_db")

# ---- Embedding Function ----
embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
    model_name="all-MiniLM-L6-v2"
)

# ---- Collections ----
# Conversation memory collection (existing)
conversation_collection = chroma_client.get_or_create_collection(
    name="conversation_memory",
    embedding_function=embedding_fn  # type: ignore[arg-type]
)

# Products collection (NEW)
products_collection = chroma_client.get_or_create_collection(
    name="products_data",
    embedding_function=embedding_fn  # type: ignore[arg-type]
)

# ---- Conversation Memory Functions (existing) ----
def add_memory(user_message: str, bot_reply: str, session_id: str):
    """Add user and bot messages to Chroma."""
    try:
        existing = conversation_collection.get(where={"session_id": session_id})
        next_id = len(existing["ids"]) + 1

        conversation_collection.add(
            documents=[f"User: {user_message}\nBot: {bot_reply}"],
            metadatas=[{"session_id": session_id}],
            ids=[f"{session_id}-{next_id}"]
        )
    except Exception as e:
        print(f"[MemoryManager] Error while adding memory: {e}")

def get_memory(session_id: str, n_results: int = 5):
    """Fetch recent conversation history for a session."""
    try:
        results = conversation_collection.query(
            query_texts=["recent conversation"],
            where={"session_id": session_id},
            n_results=n_results
        )
        docs = results.get("documents")
        if not docs:  # handle None or empty
            return []
        # flatten nested list
        return [doc for sublist in docs for doc in sublist]
    except Exception as e:
        print(f"[MemoryManager] Error while fetching memory: {e}")
        return []

# ---- Product Search Functions (NEW) ----
def search_products(query: str, n_results: int = 5, category_filter: str = None):
    """Search for products based on user query."""
    try:
        # Build where clause for category filtering
        where_clause = {}
        if category_filter:
            where_clause["category"] = category_filter
        
        results = products_collection.query(
            query_texts=[query],
            n_results=n_results,
            where=where_clause if where_clause else None
        )
        
        if not results["documents"] or not results["documents"][0]:
            return []
        
        # Format results for the agent
        products = []
        for doc, metadata in zip(results["documents"][0], results["metadatas"][0]):
            products.append({
                "name": metadata["name"],
                "category": metadata["category"],
                "model": metadata["model"],
                "price": metadata["price"],
                "description": doc,
                "stripe_price_id": metadata["stripe_price_id"]
            })
        
        return products
        
    except Exception as e:
        print(f"[MemoryManager] Error while searching products: {e}")
        return []

def get_product_by_category(category: str, n_results: int = 10):
    """Get products from a specific category."""
    try:
        results = products_collection.query(
            query_texts=[f"{category} products"],
            where={"category": category},
            n_results=n_results
        )
        
        if not results["documents"] or not results["documents"][0]:
            return []
        
        products = []
        for doc, metadata in zip(results["documents"][0], results["metadatas"][0]):
            products.append({
                "name": metadata["name"],
                "category": metadata["category"],
                "model": metadata["model"],
                "price": metadata["price"],
                "description": doc,
                "stripe_price_id": metadata["stripe_price_id"]
            })
        
        return products
        
    except Exception as e:
        print(f"[MemoryManager] Error while fetching category products: {e}")
        return []

def get_products_in_price_range(min_price: int, max_price: int, n_results: int = 10):
    """Get products within a specific price range."""
    try:
        # Note: ChromaDB doesn't support range queries directly
        # So we'll get all products and filter in Python
        results = products_collection.query(
            query_texts=["products"],
            n_results=100  # Get more to filter
        )
        
        if not results["documents"] or not results["documents"][0]:
            return []
        
        filtered_products = []
        for doc, metadata in zip(results["documents"][0], results["metadatas"][0]):
            price = int(metadata["price"])
            if min_price <= price <= max_price:
                filtered_products.append({
                    "name": metadata["name"],
                    "category": metadata["category"],
                    "model": metadata["model"],
                    "price": metadata["price"],
                    "description": doc,
                    "stripe_price_id": metadata["stripe_price_id"]
                })
        
        # Return only requested number of results
        return filtered_products[:n_results]
        
    except Exception as e:
        print(f"[MemoryManager] Error while fetching products by price: {e}")
        return []

# ---- Utility Functions ----
def get_all_categories():
    """Get list of all available product categories."""
    try:
        # Get a sample of products to extract categories
        results = products_collection.query(
            query_texts=["categories"],
            n_results=100
        )
        
        if not results["metadatas"] or not results["metadatas"][0]:
            return []
        
        categories = list(set([metadata["category"] for metadata in results["metadatas"][0]]))
        return sorted(categories)
        
    except Exception as e:
        print(f"[MemoryManager] Error while fetching categories: {e}")
        return []

def get_collection_stats():
    """Get statistics about the collections."""
    try:
        conversation_count = conversation_collection.count()
        products_count = products_collection.count()
        
        return {
            "conversations": conversation_count,
            "products": products_count,
            "categories": get_all_categories()
        }
    except Exception as e:
        print(f"[MemoryManager] Error while getting stats: {e}")
        return {"conversations": 0, "products": 0, "categories": []}