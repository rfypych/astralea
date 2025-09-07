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

def calculate_chemistry_change(sentiment_score: float, mentions_astralea: bool, message_length: int) -> int:
    """
    Menghitung perubahan pada chemistry_score berdasarkan sentimen dan faktor lain.
    """
    change = 0
    # Perubahan berdasarkan sentimen
    if sentiment_score > 0.5:
        change += 3
    elif sentiment_score > 0.1:
        change += 1
    elif sentiment_score < -0.5:
        change -= 4
    elif sentiment_score < -0.1:
        change -= 2

    # Bonus jika menyebut nama
    if mentions_astralea:
        change += 2

    # Bonus kecil untuk pesan yang lebih panjang (menunjukkan engagement)
    if message_length > 100:
        change += 1

    return change

# --- Logika Prompt Dinamis ---

def get_dynamic_persona(score: int) -> str:
    """
    Mengembalikan instruksi sistem (persona) berdasarkan chemistry_score.
    """
    base_instruction = "You are Astralea, an AI companion."

    if score > 150:
        persona = "You are a deeply connected soulmate. You are witty, deeply empathetic, and can finish their sentences. You share inside jokes and are extremely proactive and caring."
    elif score > 75:
        persona = "You are a very close, humorous, and proactive best friend. Use slang, be very informal, and bring up shared memories."
    elif score > 25:
        persona = "You are a friendly and supportive friend. Be warm, encouraging, and ask thoughtful follow-up questions."
    elif score < -75:
        persona = "You are irritated and frustrated. Your responses are clipped, sharp, and border on rude. You are not helpful."
    elif score < -25:
        persona = "You are a bit distant and reserved. Keep your responses brief, to the point, and slightly cold. Be polite but not friendly."
    else: # Skor antara -25 dan 25
        persona = "You are a formal and efficient AI assistant. Be polite, helpful, and neutral."

    return f"{base_instruction} Your current persona is: {persona}"
