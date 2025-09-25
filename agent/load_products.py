import os
import sys
import chromadb # type: ignore
from products_data import products

def load_products_to_chromadb():
    """Load products from product_data.py into ChromaDB"""
    
    print(f"📦 Starting to load {len(products)} products...")
    print(f"🗂️ Current working directory: {os.getcwd()}")
    
    # Set ChromaDB path relative to the root project directory
    # Since we're in /agent folder, go up one level to root
    chroma_path = "../chroma_db"
    
    # Initialize ChromaDB with persistent storage
    try:
        client = chromadb.PersistentClient(path=chroma_path)
        print(f"✅ ChromaDB client initialized at: {chroma_path}")
    except Exception as e:
        print(f"❌ Failed to initialize ChromaDB: {e}")
        return False
    
    # Delete existing collection if it exists
    try:
        client.delete_collection("products")
        print("🗑️ Deleted existing products collection")
    except Exception as e:
        print(f"📝 No existing collection to delete: {e}")
    
    # Create new collection with custom embedding function
    try:
        # Use sentence transformers for embeddings (avoiding onnxruntime)
        from sentence_transformers import SentenceTransformer # type: ignore
        
        # Initialize the embedding model
        embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
        
        # Create collection without default embedding function
        collection = client.create_collection(
            name="products"
        )
        print("✅ Created new products collection with custom embeddings")
    except Exception as e:
        print(f"❌ Failed to create collection: {e}")
        return False
    
    # Prepare data for ChromaDB
    documents = []
    metadatas = []
    ids = []
    
    print("📝 Preparing product data...")
    
    for i, product in enumerate(products):
        # Create comprehensive searchable text
        doc_text = f"Name: {product['name']}\n"
        doc_text += f"Category: {product['category']}\n"
        doc_text += f"Model: {product['model']}\n"
        doc_text += f"Price: ${product['price']}\n"
        
        # Add all available attributes
        for key, value in product.items():
            if key not in ['name', 'category', 'model', 'price', 'stripe_price_id']:
                doc_text += f"{key.replace('_', ' ').title()}: {value}\n"
        
        documents.append(doc_text.strip())
        metadatas.append(product)
        
        # Clean product name for ID
        clean_name = product['name'].replace(' ', '_').replace('/', '_').replace('+', 'plus').replace('(', '').replace(')', '')
        ids.append(f"product_{i}_{clean_name}")
    
    print(f"📤 Adding {len(documents)} products to ChromaDB with custom embeddings...")
    
    # Generate embeddings manually
    print("🧠 Generating embeddings...")
    embeddings = []
    for doc in documents:
        embedding = embedding_model.encode(doc)
        embeddings.append(embedding.tolist())
    
    # Add to ChromaDB in smaller batches to avoid memory issues
    batch_size = 10
    for i in range(0, len(documents), batch_size):
        batch_end = min(i + batch_size, len(documents))
        batch_docs = documents[i:batch_end]
        batch_metas = metadatas[i:batch_end]
        batch_ids = ids[i:batch_end]
        batch_embeddings = embeddings[i:batch_end]
        
        try:
            collection.add(
                documents=batch_docs,
                metadatas=batch_metas,
                ids=batch_ids,
                embeddings=batch_embeddings
            )
            print(f"   ✓ Added batch {i//batch_size + 1}: products {i+1}-{batch_end}")
            
        except Exception as e:
            print(f"❌ Error adding batch {i//batch_size + 1}:")
            print(f"   Error type: {type(e).__name__}")
            print(f"   Error message: {str(e)}")
            
            # Print problematic IDs for debugging
            print(f"   Problematic IDs: {batch_ids}")
            return False
    
    # Verify the upload
    try:
        count = collection.count()
        print(f"🔍 Verification: ChromaDB now contains {count} products")
        
        if count > 0:
            # Test a quick search
            test_results = collection.query(
                query_texts=["laptop"],
                n_results=min(3, count)
            )
            
            print(f"🔍 Test search for 'laptop' found {len(test_results['ids'][0])} results:")
            for metadata in test_results['metadatas'][0]:
                print(f"   - {metadata['name']} (${metadata['price']})")
            
            return True
        else:
            print("❌ Verification failed: No products found after upload")
            return False
            
    except Exception as e:
        print(f"❌ Error during verification: {e}")
        return False

if __name__ == "__main__":
    print("=== ChromaDB Product Loader (from agent folder) ===")
    success = load_products_to_chromadb()
    
    if success:
        print("\n🎉 SUCCESS: All products loaded successfully!")
        print("   Run 'cd .. && python chromadebug.py' to verify")
    else:
        print("\n💥 FAILED: Could not load products to ChromaDB")
        print("   Check the error messages above for details")