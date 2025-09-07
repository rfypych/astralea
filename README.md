# AI Chatbot "Astralea"

Project "Astralea" adalah sebuah AI chatbot percakapan yang dirancang untuk membangun "chemistry" atau hubungan kontekstual dengan pengguna. Fitur utamanya meliputi memori kontekstual, kepribadian adaptif, dan indikator chemistry yang dinamis.

## Arsitektur

Proyek ini menggunakan arsitektur monorepo dengan dua komponen utama:

-   `backend/`: Aplikasi API yang dibangun dengan **Python/FastAPI**. Bertanggung jawab untuk logika inti, koneksi ke LLM (Mistral AI), manajemen memori (ChromaDB), dan Mesin Emosi.
-   `frontend/`: Aplikasi web yang dibangun dengan **Next.js/TypeScript**. Bertanggung jawab untuk antarmuka pengguna (UI), interaksi, dan autentikasi pengguna (Supabase Auth).

---

## Prasyarat

Sebelum menjalankan proyek ini, Anda perlu menyiapkan beberapa hal berikut:

### 1. Akun Layanan Pihak Ketiga (Gratis)

-   **Mistral AI**: Untuk model bahasa.
-   **Supabase**: Untuk database relasional dan autentikasi.
-   **Render**: Untuk hosting backend.
-   **Vercel**: Untuk hosting frontend.

### 2. Konfigurasi Supabase

Setelah membuat proyek di Supabase, Anda **harus** melakukan konfigurasi database berikut:

a. Buka **SQL Editor** di dashboard Supabase Anda.
b. Jalankan skrip berikut untuk membuat tabel `profiles` yang akan menyimpan data spesifik pengguna seperti `chemistry_score`.

```sql
-- Membuat tabel profiles untuk menyimpan data publik pengguna
CREATE TABLE public.profiles (
  id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
  username TEXT UNIQUE,
  updated_at TIMESTAMP WITH TIME ZONE,
  chemistry_score INTEGER DEFAULT 0,

  CONSTRAINT username_length CHECK (char_length(username) >= 3)
);

-- Kebijakan RLS (Row Level Security)
-- 1. Izinkan pengguna membaca profil mereka sendiri
CREATE POLICY "Users can read their own profile."
  ON public.profiles FOR SELECT
  USING ( auth.uid() = id );

-- 2. Izinkan pengguna untuk membuat profil mereka sendiri
CREATE POLICY "Users can create their own profile."
  ON public.profiles FOR INSERT
  WITH CHECK ( auth.uid() = id );

-- 3. Izinkan pengguna untuk memperbarui profil mereka sendiri
CREATE POLICY "Users can update their own profile."
  ON public.profiles FOR UPDATE
  USING ( auth.uid() = id );

-- Fungsi untuk menangani pembuatan profil baru secara otomatis
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER AS $$
BEGIN
  INSERT INTO public.profiles (id, username)
  VALUES (new.id, new.email); -- Default username ke email
  RETURN new;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Trigger yang memanggil fungsi di atas setiap kali ada pengguna baru
CREATE TRIGGER on_auth_user_created
  AFTER INSERT ON auth.users
  FOR EACH ROW EXECUTE PROCEDURE public.handle_new_user();
```

### 3. Variabel Lingkungan

Buat file `.env` di dalam direktori `backend/` dan isi dengan variabel berikut:

```
MISTRAL_API_KEY="YOUR_MISTRAL_API_KEY"
SUPABASE_URL="YOUR_SUPABASE_PROJECT_URL"
SUPABASE_KEY="YOUR_SUPABASE_ANON_KEY"
```

---

## Menjalankan Proyek Secara Lokal

### Backend (FastAPI)

1.  Masuk ke direktori backend: `cd backend`
2.  Buat dan aktifkan virtual environment: `python -m venv venv` dan `source venv/bin/activate` (atau `venv\Scripts\activate` di Windows).
3.  Install dependensi: `pip install -r requirements.txt`
4.  Jalankan server: `uvicorn main:app --reload`
5.  Server akan berjalan di `http://127.0.0.1:8000`.

### Frontend (Next.js)

1.  Masuk ke direktori frontend: `cd frontend`
2.  Install dependensi: `npm install`
3.  Jalankan server pengembangan: `npm run dev`
4.  Aplikasi akan berjalan di `http://localhost:3000`.
