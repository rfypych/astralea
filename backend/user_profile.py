import json
from typing import List

from auth import supabase
from llm import call_mistral_api

def extract_and_update_interests(user_id: str, conversation_history: List[str]):
    """
    Mengekstrak minat dari transkrip percakapan dan memperbaruinya di profil pengguna.
    """
    if not conversation_history:
        return

    # Gabungkan riwayat menjadi satu teks
    transcript = "\n".join(conversation_history)

    # Buat prompt untuk LLM
    prompt = f"""
    Based on the following conversation transcript, please extract the main topics of interest for the user.
    Focus on specific nouns, concepts, hobbies, or proper names.
    Return your answer as a single, flat JSON array of strings. For example: ["sci-fi movies", "cat care", "python programming"].
    If no clear topics are found, return an empty array.

    Transcript:
    ---
    {transcript}
    ---
    """

    # Panggil LLM untuk ekstraksi
    # Kita bisa menggunakan model yang lebih besar/pintar jika 'tiny' tidak cukup
    response_text = call_mistral_api(prompt, model="mistral-small")

    try:
        # Coba parsing JSON dari respons
        extracted_interests = json.loads(response_text)
        if not isinstance(extracted_interests, list):
            print(f"WARNING: LLM did not return a list for user {user_id}. Got: {response_text}")
            return
    except json.JSONDecodeError:
        print(f"WARNING: Failed to decode JSON from LLM response for user {user_id}. Response: {response_text}")
        return

    if not extracted_interests:
        print(f"INFO: No new interests extracted for user {user_id}.")
        return

    # Ambil minat yang sudah ada dari DB
    profile_res = supabase.table('profiles').select('user_interests').eq('id', user_id).single().execute()
    existing_interests_str = profile_res.data.get('user_interests')

    existing_interests = set()
    if existing_interests_str:
        try:
            # Muat minat yang ada, pastikan itu adalah list
            loaded_interests = json.loads(existing_interests_str)
            if isinstance(loaded_interests, list):
                existing_interests = set(loaded_interests)
        except json.JSONDecodeError:
            print(f"WARNING: Could not parse existing interests for user {user_id}.")

    # Gabungkan dengan minat baru, hindari duplikat
    new_interests_set = set(extracted_interests)
    updated_interests = list(existing_interests.union(new_interests_set))

    # Simpan kembali ke DB
    supabase.table('profiles').update({'user_interests': json.dumps(updated_interests)}).eq('id', user_id).execute()
    print(f"INFO: Updated interests for user {user_id}. New list: {updated_interests}")
