import chromadb # type: ignore
import json
import os

def debug_chromadb():
    print("=== ChromaDB Debug Test ===\n")
    
    try:
        # Make sure we're using the same path as load_products.py
        client = chromadb.PersistentClient(path="./chroma_db")
        print(f"✅ ChromaDB client initialized with path: ./chroma_db")
        
        # Check if chroma_db directory exists
        if os.path.exists("./chroma_db"):
            print(f"✅ ChromaDB directory exists")
            files = os.listdir("./chroma_db")
            print(f"📁 Directory contents: {files}")
        else:
            print(f"❌ ChromaDB directory does not exist!")
        
    except Exception as e:
        print(f"❌ Error initializing ChromaDB client: {e}")
        return
    
    try:
        # Get the products collection
        collection = client.get_collection("products")
        print(f"✅ Products collection found")
        
    except Exception as e:
        print(f"❌ Error getting products collection: {e}")
        print("   Try creating collection with: collection = client.get_or_create_collection('products')")
        
        # Try to create collection if it doesn't exist
        try:
            collection = client.get_or_create_collection("products")
            print(f"✅ Created products collection")
        except Exception as e2:
            print(f"❌ Error creating collection: {e2}")
            return
    
    # Check collection statistics
    try:
        count = collection.count()
        print(f"\n1. Collection Statistics:")
        print(f"   Products in ChromaDB: {count}")
        
        if count > 0:
            # Get a sample of products
            results = collection.get(limit=5)
            print(f"   Sample products loaded: {len(results['ids'])}")
            
            # Show categories
            categories = set()
            for metadata in results['metadatas']:
                if 'category' in metadata:
                    categories.add(metadata['category'])
            
            print(f"   Categories available: {list(categories)}")
            
            # Show first product as example
            if results['metadatas']:
                print(f"\n   Example product:")
                first_product = results['metadatas'][0]
                print(f"   - Name: {first_product.get('name', 'N/A')}")
                print(f"   - Category: {first_product.get('category', 'N/A')}")
                print(f"   - Price: ${first_product.get('price', 'N/A')}")
        else:
            print(f"   Categories available: []")
            print(f"   ❌ ERROR: No products found in ChromaDB!")
            print(f"   Solution: Run 'python load_products.py' again")
            
    except Exception as e:
        print(f"❌ Error getting collection statistics: {e}")
        return
    
    # Test search functionality
    if count > 0:
        try:
            print(f"\n2. Search Test:")
            search_results = collection.query(
                query_texts=["laptop computer"],
                n_results=3
            )
            
            print(f"   Search for 'laptop computer' returned {len(search_results['ids'][0])} results")
            
            for i, metadata in enumerate(search_results['metadatas'][0]):
                print(f"   - {metadata.get('name', 'N/A')} (${metadata.get('price', 'N/A')})")
                
        except Exception as e:
            print(f"❌ Error testing search: {e}")
    
    # Final status
    if count > 0:
        print(f"\n✅ ChromaDB is working correctly with {count} products")
    else:
        print(f"\n❌ ChromaDB has issues - products not found")

if __name__ == "__main__":
    debug_chromadb()