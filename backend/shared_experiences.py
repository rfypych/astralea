import re
import requests
from bs4 import BeautifulSoup
import json

from auth import supabase

# --- Regex untuk Deteksi Tautan ---
IMDB_REGEX = r'(https?://www.imdb.com/title/(tt\d+))'
SPOTIFY_REGEX = r'(https?://open.spotify.com/track/([a-zA-Z0-9]+))'

def scrape_imdb_metadata(url: str) -> dict | None:
    """Mengambil metadata dasar dari halaman IMDB."""
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')

        title = soup.find('h1').text.strip()
        # Cari tahun dari elemen yang sama atau di dekatnya
        year_span = soup.find('h1').find_next_sibling('div').find('a')
        year = year_span.text.strip() if year_span else "N/A"

        return {"title": title, "year": year, "url": url}
    except Exception as e:
        print(f"ERROR: Failed to scrape IMDB URL {url}: {e}")
        return None

def scrape_spotify_metadata(url: str) -> dict | None:
    """Mengambil metadata dasar dari halaman Spotify."""
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')

        title = soup.find('meta', property='og:title')['content']
        artist = soup.find('meta', property='og:description')['content'].split('·')[0].strip()

        return {"title": title, "artist": artist, "url": url}
    except Exception as e:
        print(f"ERROR: Failed to scrape Spotify URL {url}: {e}")
        return None

def process_and_store_shared_experience(user_id: str, message: str):
    """
    Mendeteksi tautan, mengambil metadata, dan menyimpannya ke DB.
    """
    imdb_match = re.search(IMDB_REGEX, message)
    spotify_match = re.search(SPOTIFY_REGEX, message)

    activity_type = None
    metadata = None

    if imdb_match:
        activity_type = "movie"
        metadata = scrape_imdb_metadata(imdb_match.group(1))
    elif spotify_match:
        activity_type = "song"
        metadata = scrape_spotify_metadata(spotify_match.group(1))

    if activity_type and metadata:
        try:
            supabase.table('shared_experiences').insert({
                "user_id": user_id,
                "activity_type": activity_type,
                "item_details": metadata
            }).execute()
            print(f"INFO: Stored shared experience '{activity_type}' for user {user_id}: {metadata['title']}")
        except Exception as e:
            print(f"ERROR: Failed to insert shared experience to DB for user {user_id}: {e}")
