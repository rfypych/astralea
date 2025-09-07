import os
import requests

# --- Konfigurasi Mistral AI ---
MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")
MISTRAL_API_URL = "https://api.mistral.ai/v1/chat/completions"

def call_mistral_api(prompt: str, model: str = "mistral-tiny", image_url: str | None = None) -> str:
    """
    Melakukan panggilan ke Mistral AI API, dengan dukungan multimodal opsional.
    """
    if not MISTRAL_API_KEY:
        error_msg = "ERROR: MISTRAL_API_KEY not set. Please configure the environment variable."
        print(error_msg)
        return error_msg

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {MISTRAL_API_KEY}"
    }

    # Tentukan model dan konten pesan berdasarkan adanya gambar
    if image_url:
        # Gunakan model yang mendukung multimodal
        api_model = "mistral-large-latest"
        content = [
            {"type": "image_url", "image_url": {"url": image_url}},
            {"type": "text", "text": prompt},
        ]
    else:
        api_model = model
        content = prompt

    data = {
        "model": api_model,
        "messages": [{"role": "user", "content": content}]
    }

    try:
        response = requests.post(MISTRAL_API_URL, headers=headers, json=data, timeout=45)
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]
    except requests.exceptions.RequestException as e:
        print(f"ERROR: Mistral API call failed: {e}")
        return f"Sorry, I encountered an error while contacting my brain (Mistral API). Error: {e}"
    except (KeyError, IndexError) as e:
        print(f"ERROR: Invalid response format from Mistral API: {e}")
        return "Sorry, I received an unexpected response from my brain. Please try again."
