import chromadb
from sentence_transformers import SentenceTransformer
import uuid

# --- Inisialisasi Model & Database ---

# Inisialisasi klien ChromaDB. Data akan disimpan di disk.
# Di Render, ini akan berada di disk persisten.
client = chromadb.PersistentClient(path="./chroma_db")

# Inisialisasi model embedding. 'all-MiniLM-L6-v2' adalah model yang bagus dan ringan.
embedding_model = SentenceTransformer('all-MiniLM-L6-v2', device='cpu')

# Dapatkan atau buat koleksi (mirip tabel di SQL) untuk menyimpan memori.
# Ini memastikan kita tidak membuat ulang koleksi setiap kali server dimulai.
try:
    memory_collection = client.get_collection(name="astralea_memories")
except ValueError:
    memory_collection = client.create_collection(name="astralea_memories")

# --- Fungsi-fungsi Memori ---

def add_memory(user_id: str, user_message: str, ai_response: str):
    """
    Menyimpan satu putaran percakapan (user + AI) ke dalam database vektor.
    """
    conversation_text = f"User said: '{user_message}'. Astralea responded: '{ai_response}'."
    embedding = embedding_model.encode(conversation_text).tolist()

    # Kita menggunakan UUID untuk ID unik setiap entri memori.
    memory_id = str(uuid.uuid4())

    memory_collection.add(
        ids=[memory_id],
        embeddings=[embedding],
        documents=[conversation_text],
        metadatas=[{"user_id": user_id}]
    )
    print(f"INFO: Added memory for user {user_id}.")

def retrieve_memories(user_id: str, query_message: str, num_results: int = 3) -> str:
    """
    Mengambil beberapa memori paling relevan untuk pengguna berdasarkan pesan terbaru mereka.
    """
    if not query_message:
        return ""

    query_embedding = embedding_model.encode(query_message).tolist()

    try:
        results = memory_collection.query(
            query_embeddings=[query_embedding],
            n_results=num_results,
            where={"user_id": user_id} # Filter berdasarkan user_id
        )

        retrieved_docs = results['documents'][0]
        if retrieved_docs:
            formatted_memories = "\n- ".join(retrieved_docs)
            print(f"INFO: Retrieved {len(retrieved_docs)} memories for user {user_id}.")
            return f"Here are some relevant past conversations:\n- {formatted_memories}"
        else:
            return ""

    except Exception as e:
        print(f"ERROR: Failed to retrieve memories for user {user_id}. Error: {e}")
        return ""
