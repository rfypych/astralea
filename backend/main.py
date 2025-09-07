import os
import requests
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
from gotrue.types import User

# Impor modul lokal
from memory import add_memory, retrieve_memories
from auth import get_current_user, supabase
from emotion_engine import analyze_sentiment_hybrid, calculate_chemistry_change, get_dynamic_persona

# Muat variabel lingkungan dari file .env
load_dotenv()

app = FastAPI(
    title="Astralea AI Chatbot",
    description="Backend for Astralea, the emotional AI chatbot.",
    version="1.0.0"
)

# --- Konfigurasi CORS ---
origins = ["http://localhost:3000", os.getenv("FRONTEND_URL", "")]
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin for origin in origins if origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Model Pydantic ---
class ChatRequest(BaseModel):
    message: str

class ChatResponse(BaseModel):
    response: str
    chemistry_score: int

# --- Logika Inti ---
MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")
MISTRAL_API_URL = "https://api.mistral.ai/v1/chat/completions"

def call_mistral_api(prompt: str) -> str:
    if not MISTRAL_API_KEY:
        return "ERROR: MISTRAL_API_KEY not set."
    headers = {"Authorization": f"Bearer {MISTRAL_API_KEY}", "Content-Type": "application/json"}
    data = {"model": "mistral-tiny", "messages": [{"role": "user", "content": prompt}]}
    try:
        response = requests.post(MISTRAL_API_URL, headers=headers, json=data, timeout=30)
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]
    except Exception as e:
        print(f"ERROR: Mistral API call failed: {e}")
        return "Sorry, I'm having trouble thinking right now."

# --- Endpoint API ---
@app.get("/")
def read_root():
    return {"message": "Welcome to the Astralea AI Backend"}

@app.post("/api/chat", response_model=ChatResponse)
async def chat_with_ai(request: ChatRequest, current_user: User = Depends(get_current_user)):
    """
    Endpoint obrolan utama yang aman dan dinamis.
    """
    user_id = str(current_user.id)
    user_message = request.message

    # 1. Ambil skor chemistry saat ini dari DB
    profile_res = supabase.table('profiles').select('chemistry_score').eq('id', user_id).single().execute()
    current_score = profile_res.data.get('chemistry_score', 0)

    # 2. Hitung skor baru dengan Mesin Emosi
    sentiment_score = analyze_sentiment_hybrid(user_message)
    mentions_astralea = 'astralea' in user_message.lower()
    score_change = calculate_chemistry_change(sentiment_score, mentions_astralea)
    new_score = current_score + score_change

    # 3. Dapatkan persona dinamis berdasarkan skor baru
    system_prompt = get_dynamic_persona(new_score)

    # 4. Ambil memori yang relevan (RAG)
    retrieved_context = retrieve_memories(user_id, user_message)

    # 5. Bangun prompt akhir
    prompt_parts = [system_prompt]
    if retrieved_context:
        prompt_parts.append(f"\n--- Relevant Past Conversations ---\n{retrieved_context}\n---------------------------------")
    prompt_parts.append(f"\nNew message from user: '{user_message}'")
    final_prompt = "\n".join(prompt_parts)

    # 6. Panggil LLM
    ai_response = call_mistral_api(final_prompt)

    # 7. Simpan memori baru & perbarui skor di DB
    add_memory(user_id, user_message, ai_response)
    supabase.table('profiles').update({'chemistry_score': new_score}).eq('id', user_id).execute()

    print(f"INFO: User {user_id} score changed from {current_score} to {new_score}. Persona: {system_prompt.split(': ')[-1]}")

    return ChatResponse(response=ai_response, chemistry_score=new_score)
