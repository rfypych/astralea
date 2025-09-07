from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

# --- Inisialisasi ---
vader_analyzer = SentimentIntensityAnalyzer()

# --- Analisis Sentimen Hibrida (Inggris & Indonesia) ---

# Daftar kata kunci sederhana untuk Bahasa Indonesia
# Ini bisa diperluas secara signifikan.
INDONESIAN_POSITIVE_KEYWORDS = ['suka', 'bagus', 'baik', 'keren', 'hebat', 'terima kasih', 'makasih', 'setuju']
INDONESIAN_NEGATIVE_KEYWORDS = ['tidak suka', 'benci', 'buruk', 'jelek', 'masalah']

def analyze_sentiment_hybrid(text: str) -> float:
    """
    Menganalisis sentimen teks. Menggunakan VADER untuk B. Inggris dan kata kunci untuk B. Indonesia.
    Mengembalikan skor compound antara -1 (sangat negatif) dan 1 (sangat positif).
    """
    text_lower = text.lower()

    # Deteksi bahasa yang sangat sederhana
    is_indonesian = any(keyword in text_lower for keyword in INDONESIAN_POSITIVE_KEYWORDS + INDONESIAN_NEGATIVE_KEYWORDS)

    if is_indonesian:
        score = 0
        for keyword in INDONESIAN_POSITIVE_KEYWORDS:
            if keyword in text_lower:
                score += 0.5
        for keyword in INDONESIAN_NEGATIVE_KEYWORDS:
            if keyword in text_lower:
                score -= 0.6
        # Batasi skor antara -1 dan 1
        return max(-1.0, min(1.0, score))
    else:
        # Gunakan VADER untuk bahasa Inggris (dan sebagai default)
        vs = vader_analyzer.polarity_scores(text)
        return vs['compound']

# --- Logika Skor Chemistry ---

def calculate_chemistry_change(sentiment_score: float, mentions_astralea: bool) -> int:
    """
    Menghitung perubahan pada chemistry_score berdasarkan sentimen dan faktor lain.
    """
    change = 0
    if sentiment_score > 0.5:
        change += 3  # Sangat positif
    elif sentiment_score > 0.1:
        change += 1  # Agak positif
    elif sentiment_score < -0.5:
        change -= 4  # Sangat negatif
    elif sentiment_score < -0.1:
        change -= 2  # Agak negatif

    if mentions_astralea:
        change += 2 # Bonus jika menyebut nama

    return change

# --- Logika Prompt Dinamis ---

def get_dynamic_persona(score: int) -> str:
    """
    Mengembalikan instruksi sistem (persona) berdasarkan chemistry_score.
    """
    base_instruction = "You are Astralea, an AI companion."

    if score > 75:
        persona = "You are a very close, humorous, and proactive best friend. Use slang and be very informal."
    elif score > 25:
        persona = "You are a friendly and supportive friend. Be warm and encouraging."
    elif score < -25:
        persona = "You are a bit distant and reserved. Keep your responses brief and to the point. Be polite but not overly friendly."
    else: # Skor antara -25 dan 25
        persona = "You are a formal and efficient AI assistant. Be polite and helpful."

    return f"{base_instruction} Your current persona is: {persona}"
