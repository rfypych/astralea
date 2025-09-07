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
from memory import add_memory, retrieve_memories, retrieve_shared_experiences
from auth import get_current_user, supabase
from emotion_engine import analyze_sentiment_hybrid, calculate_chemistry_change, get_dynamic_persona
from llm import call_mistral_api
from user_profile import extract_and_update_interests
from tools import AVAILABLE_TOOLS
from shared_experiences import process_and_store_shared_experience

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
    image_url: str | None = None

class ChatResponse(BaseModel):
    response: str
    chemistry_score: int

# --- Endpoint API ---
@app.get("/")
def read_root():
    return {"message": "Welcome to the Astralea AI Backend v2.0"}

# --- Alur Penggunaan Alat (ReAct) ---

def run_tool_use_flow(user_message: str) -> str | None:
    """
    Menjalankan alur ReAct: Nalar -> Bertindak -> Sintesis.
    Mengembalikan respons akhir jika alat digunakan, jika tidak, None.
    """
    # 1. Nalar (Reason): Tentukan apakah alat diperlukan
    tool_reasoning_prompt = f"""
    You are a helpful AI assistant with access to the following tools:
    - get_weather(city: str): Get the current weather for a city.
    - get_latest_news(topic: str): Get recent news headlines about a topic.

    Analyze the user's message: "{user_message}"
    Does this message require the use of a tool?
    If yes, respond with a single JSON object with "tool_name" and "parameters" keys.
    Example: {{"tool_name": "get_weather", "parameters": {{"city": "London"}}}}
    If no, respond with the exact text "NO_TOOL".
    """

    tool_choice_response = call_mistral_api(tool_reasoning_prompt, model="mistral-small")

    if "NO_TOOL" in tool_choice_response:
        print("INFO: Tool not required for this query.")
        return None

    try:
        tool_data = json.loads(tool_choice_response)
        tool_name = tool_data.get("tool_name")
        parameters = tool_data.get("parameters", {})

        if tool_name not in AVAILABLE_TOOLS:
            print(f"WARNING: LLM requested an unknown tool: {tool_name}")
            return None

    except (json.JSONDecodeError, AttributeError):
        print(f"WARNING: Could not parse tool use response: {tool_choice_response}")
        return None

    # 2. Bertindak (Act): Jalankan alat yang dipilih
    print(f"INFO: Executing tool '{tool_name}' with params {parameters}")
    tool_function = AVAILABLE_TOOLS[tool_name]
    try:
        tool_result = tool_function(**parameters)
    except TypeError as e:
        print(f"ERROR: Tool parameter mismatch for {tool_name}: {e}")
        return f"I tried to use my {tool_name} tool, but I seem to have the wrong parameters."

    # 3. Sintesis (Synthesize): Hasilkan respons akhir berdasarkan hasil alat
    synthesis_prompt = f"""
    You are Astralea, a friendly AI. Your goal is to give a natural, conversational response.
    A user asked: "{user_message}"
    You used the '{tool_name}' tool and got this result:
    ---
    {tool_result}
    ---
    Based on this data, formulate a helpful and friendly response to the user.
    """

    final_response = call_mistral_api(synthesis_prompt)
    print(f"INFO: Synthesized tool response: {final_response}")
    return final_response


@app.post("/api/chat", response_model=ChatResponse)
async def chat_with_ai(request: ChatRequest, background_tasks: BackgroundTasks, current_user: User = Depends(get_current_user)):
    user_id = str(current_user.id)
    user_message = request.message

    # --- LANGKAH 0: Alur Penggunaan Alat ---
    # Coba jalankan alur alat terlebih dahulu. Jika berhasil, kembalikan responsnya.
    if not request.image_url: # Penggunaan alat tidak dipicu jika ada gambar
        tool_response = run_tool_use_flow(user_message)
        if tool_response:
            # Jika alat digunakan, kita tetap ingin memperbarui skor dan memori
            profile_res = supabase.table('profiles').select('chemistry_score').eq('id', user_id).single().execute()
            current_score = profile_res.data.get('chemistry_score', 0) if profile_res.data else 0

            # Perubahan skor netral untuk penggunaan alat
            new_score = current_score + 1

            add_memory(user_id, user_message, tool_response)
            supabase.table('profiles').update({
                'chemistry_score': new_score,
                'last_seen': datetime.utcnow().isoformat()
            }).eq('id', user_id).execute()

            return ChatResponse(response=tool_response, chemistry_score=new_score)

    # --- Alur Obrolan Normal (jika tidak ada alat yang digunakan) ---
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

    # 4. Ambil memori yang relevan (RAG & Pengalaman Bersama)
    retrieved_context, conversation_history = retrieve_memories(user_id, user_message, num_results=3)
    shared_experiences_context = retrieve_shared_experiences(user_id, num_results=5)

    # 5. Bangun prompt akhir dengan semua konteks
    prompt_parts = [system_prompt]
    if user_interests:
        prompt_parts.append(f"Remember, the user is interested in: {', '.join(user_interests)}.")
    if shared_experiences_context:
        prompt_parts.append(f"\n--- Shared Experiences ---\n{shared_experiences_context}\n-------------------------")
    if retrieved_context:
        prompt_parts.append(f"\n--- Relevant Past Conversations ---\n{retrieved_context}\n---------------------------------")
    prompt_parts.append(f"\nNew message from user: '{user_message}'")
    final_prompt = "\n".join(prompt_parts)

    # 6. Panggil LLM
    ai_response = call_mistral_api(final_prompt, image_url=request.image_url)

    # 7. Jalankan tugas latar belakang
    background_tasks.add_task(add_memory, user_id, user_message, ai_response)
    background_tasks.add_task(process_and_store_shared_experience, user_id, user_message)

    # Perbarui profil di DB
    supabase.table('profiles').update({
        'chemistry_score': new_score,
        'last_seen': datetime.utcnow().isoformat()
    }).eq('id', user_id).execute()

    # Picu ekstraksi minat jika ambang batas tercapai
    message_counters[user_id] = message_counters.get(user_id, 0) + 1
    if message_counters[user_id] >= INTEREST_EXTRACTION_THRESHOLD:
        print(f"INFO: Interest extraction triggered for user {user_id}.")
        _, history_for_extraction = retrieve_memories(user_id, "", num_results=10)
        background_tasks.add_task(extract_and_update_interests, user_id, history_for_extraction)
        message_counters[user_id] = 0

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
