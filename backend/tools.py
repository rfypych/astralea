import os
import requests
import json

# --- Konfigurasi Kunci API Alat ---
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")
NEWSAPI_API_KEY = os.getenv("NEWSAPI_API_KEY")

# --- Definisi Alat ---

def get_weather(city: str) -> str:
    """
    Mendapatkan kondisi cuaca saat ini untuk kota tertentu menggunakan OpenWeatherMap API.
    """
    if not OPENWEATHER_API_KEY:
        return "Error: OpenWeatherMap API key is not configured."

    api_url = f"http://api.openweathermap.org/data/2.5/weather?q={city}&appid={OPENWEATHER_API_KEY}&units=metric"

    try:
        response = requests.get(api_url, timeout=10)
        response.raise_for_status()
        data = response.json()

        description = data['weather'][0]['description']
        temp = data['main']['temp']

        return json.dumps({"city": city, "temperature": f"{temp}°C", "description": description})
    except requests.exceptions.RequestException as e:
        return f"Error fetching weather data: {e}"
    except (KeyError, IndexError):
        return f"Error: Could not parse weather data for '{city}'."

def get_latest_news(topic: str) -> str:
    """
    Mendapatkan berita utama terbaru untuk topik tertentu menggunakan NewsAPI.
    """
    if not NEWSAPI_API_KEY:
        return "Error: NewsAPI API key is not configured."

    api_url = f"https://newsapi.org/v2/top-headlines?q={topic}&apiKey={NEWSAPI_API_KEY}&pageSize=3"

    try:
        response = requests.get(api_url, timeout=10)
        response.raise_for_status()
        data = response.json()

        articles = data.get('articles', [])
        if not articles:
            return f"No recent news found for '{topic}'."

        # Format headlines into a JSON string
        headlines = [{"title": article['title'], "source": article['source']['name']} for article in articles]
        return json.dumps(headlines)
    except requests.exceptions.RequestException as e:
        return f"Error fetching news data: {e}"
    except (KeyError, IndexError):
        return f"Error: Could not parse news data for '{topic}'."

# --- Peta Alat ---
# Peta ini menghubungkan nama alat dengan fungsi yang sesuai.
# Penting untuk alur ReAct.
AVAILABLE_TOOLS = {
    "get_weather": get_weather,
    "get_latest_news": get_latest_news,
}
