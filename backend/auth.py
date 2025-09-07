import os
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from supabase import create_client, Client

# --- Konfigurasi Supabase ---
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError("Supabase URL and Key must be set in environment variables.")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Skema OAuth2 untuk memberitahu FastAPI cara menemukan token
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token") # tokenUrl tidak digunakan, hanya placeholder

async def get_current_user(token: str = Depends(oauth2_scheme)):
    """
    Dependensi FastAPI untuk memvalidasi token JWT dan mendapatkan data pengguna.
    Ini akan di-inject ke setiap endpoint yang memerlukan autentikasi.
    """
    try:
        # supabase-py's get_user akan memvalidasi token di sisi server Supabase
        user = supabase.auth.get_user(token)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid user credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return user
    except Exception as e:
        # Menangkap error dari Supabase jika token tidak valid atau kedaluwarsa
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid authentication credentials: {e}",
            headers={"WWW-Authenticate": "Bearer"},
        )
