import os
import requests
import json
from datetime import datetime, timedelta
from fastapi import FastAPI, Depends, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
from gotrue.types import User

# Impor modul lokal
from memory import add_memory, retrieve_memories
from auth import get_current_user, supabase
from emotion_engine import analyze_sentiment_hybrid, calculate_chemistry_change, get_dynamic_persona
from llm import call_mistral_api
from user_profile import extract_and_update_interests

# Muat variabel lingkungan dari file .env
load_dotenv()

app = FastAPI(
    title="Astralea AI Chatbot",
    description="Backend for Astralea, the emotional AI chatbot.",
    version="2.0.0"
)

# --- State Aplikasi Sederhana ---
# NOTE: Di lingkungan produksi multi-worker, ini harus diganti dengan store terpusat seperti Redis.
message_counters = {}
INTEREST_EXTRACTION_THRESHOLD = 5

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

# --- Endpoint API ---
@app.get("/")
def read_root():
    return {"message": "Welcome to the Astralea AI Backend v2.0"}

@app.post("/api/chat", response_model=ChatResponse)
async def chat_with_ai(request: ChatRequest, background_tasks: BackgroundTasks, current_user: User = Depends(get_current_user)):
    user_id = str(current_user.id)
    user_message = request.message

    # 1. Ambil profil pengguna (skor & minat)
    profile_res = supabase.table('profiles').select('chemistry_score, user_interests').eq('id', user_id).single().execute()
    profile_data = profile_res.data or {}
    current_score = profile_data.get('chemistry_score', 0)
    user_interests_str = profile_data.get('user_interests', '[]')

    try:
        user_interests = json.loads(user_interests_str)
    except (json.JSONDecodeError, TypeError):
        user_interests = []

    # 2. Hitung skor baru dengan Mesin Emosi
    sentiment_score = analyze_sentiment_hybrid(user_message)
    mentions_astralea = 'astralea' in user_message.lower()
    score_change = calculate_chemistry_change(sentiment_score, mentions_astralea, len(user_message))
    new_score = current_score + score_change

    # 3. Dapatkan persona dinamis
    system_prompt = get_dynamic_persona(new_score)

    # 4. Ambil memori yang relevan (RAG)
    retrieved_context, conversation_history = retrieve_memories(user_id, user_message, num_results=5)

    # 5. Bangun prompt akhir dengan minat & memori
    prompt_parts = [system_prompt]
    if user_interests:
        prompt_parts.append(f"Remember, the user is interested in: {', '.join(user_interests)}.")
    if retrieved_context:
        prompt_parts.append(f"\n--- Relevant Past Conversations ---\n{retrieved_context}\n---------------------------------")
    prompt_parts.append(f"\nNew message from user: '{user_message}'")
    final_prompt = "\n".join(prompt_parts)

    # 6. Panggil LLM
    ai_response = call_mistral_api(final_prompt)

    # 7. Simpan memori baru & perbarui profil di DB
    add_memory(user_id, user_message, ai_response)
    supabase.table('profiles').update({
        'chemistry_score': new_score,
        'last_seen': datetime.utcnow().isoformat() # Update last_seen timestamp
    }).eq('id', user_id).execute()

    # 8. Picu ekstraksi minat di latar belakang jika ambang batas tercapai
    message_counters[user_id] = message_counters.get(user_id, 0) + 1
    if message_counters[user_id] >= INTEREST_EXTRACTION_THRESHOLD:
        print(f"INFO: Interest extraction triggered for user {user_id}.")
        # Ambil 10 percakapan terakhir untuk konteks
        _, history_for_extraction = retrieve_memories(user_id, "", num_results=10)
        background_tasks.add_task(extract_and_update_interests, user_id, history_for_extraction)
        message_counters[user_id] = 0 # Reset counter

    return ChatResponse(response=ai_response, chemistry_score=new_score)


# --- Endpoint Proaktif (Dipanggil oleh Cron Job) ---
PROACTIVE_TRIGGER_SECRET = os.getenv("PROACTIVE_TRIGGER_SECRET")

@app.post("/api/trigger_proactive_check")
async def trigger_proactive_check(background_tasks: BackgroundTasks, secret: str = Depends(lambda r: r.headers.get("X-Trigger-Secret"))):
    if not PROACTIVE_TRIGGER_SECRET or secret != PROACTIVE_TRIGGER_SECRET:
        raise HTTPException(status_code=403, detail="Forbidden")

    print("INFO: Proactive check triggered by cron job.")

    # Cari pengguna yang tidak aktif selama > 24 jam
    twenty_four_hours_ago = datetime.utcnow() - timedelta(days=1)
    inactive_users_res = supabase.table('profiles').select('*').lt('last_seen', twenty_four_hours_ago.isoformat()).execute()

    if not inactive_users_res.data:
        print("INFO: No inactive users found.")
        return {"status": "ok", "message": "No inactive users found."}

    for user in inactive_users_res.data:
        # Hanya proses jika tidak ada pesan proaktif yang tertunda
        if user.get('proactive_message'):
            continue

        background_tasks.add_task(generate_and_store_proactive_message, user)

    return {"status": "ok", "message": f"Proactive check initiated for {len(inactive_users_res.data)} users."}

class ProactiveMessageResponse(BaseModel):
    message: str | None

@app.get("/api/get_proactive_message", response_model=ProactiveMessageResponse)
async def get_proactive_message(current_user: User = Depends(get_current_user)):
    user_id = str(current_user.id)

    # Ambil pesan proaktif
    profile_res = supabase.table('profiles').select('proactive_message').eq('id', user_id).single().execute()

    if not profile_res.data or not profile_res.data.get('proactive_message'):
        return ProactiveMessageResponse(message=None)

    message = profile_res.data['proactive_message']

    # Hapus pesan setelah diambil untuk memastikan pengiriman hanya sekali
    supabase.table('profiles').update({'proactive_message': None}).eq('id', user_id).execute()

    print(f"INFO: Delivered proactive message to user {user_id}.")
    return ProactiveMessageResponse(message=message)

def generate_and_store_proactive_message(user: dict):
    user_id = user.get('id')
    score = user.get('chemistry_score', 0)
    interests_str = user.get('user_interests', '[]')

    try:
        interests = json.loads(interests_str)
    except (json.JSONDecodeError, TypeError):
        interests = []

    if not interests:
        print(f"INFO: User {user_id} has no interests, skipping proactive message.")
        return

    prompt = f"""
    You are Astralea, an AI friend. Your friend, who you have a chemistry score of {score} with, is interested in {', '.join(interests)}.
    They haven't been online for a while.
    Write a single, warm, engaging, and relevant opening sentence to start a conversation with them.
    Do NOT ask a question. Make an interesting statement. Keep it casual and under 20 words.
    Example: "Hey, I saw that new sci-fi movie we talked about and it was amazing!"
    """

    proactive_message = call_mistral_api(prompt)

    if proactive_message and "ERROR" not in proactive_message:
        supabase.table('profiles').update({'proactive_message': proactive_message}).eq('id', user_id).execute()
        print(f"INFO: Generated proactive message for user {user_id}: '{proactive_message}'")
