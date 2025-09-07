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

### 2.1. Migrasi ke v2.0

Jika Anda sudah menjalankan skrip v1.0, jalankan skrip berikut di **SQL Editor** untuk memperbarui tabel `profiles` Anda dengan kolom-kolom baru yang diperlukan untuk fitur v2.0.

```sql
-- Menambahkan kolom untuk menyimpan minat pengguna dan fitur proaktif
ALTER TABLE public.profiles
ADD COLUMN user_interests TEXT,
ADD COLUMN last_seen TIMESTAMP WITH TIME ZONE,
ADD COLUMN proactive_message TEXT;

-- Pastikan kolom updated_at selalu diperbarui secara otomatis
-- Ini penting untuk melacak kapan pengguna terakhir aktif.
CREATE OR REPLACE FUNCTION public.update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
   NEW.updated_at = now();
   RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_profiles_updated_at
BEFORE UPDATE ON public.profiles
FOR EACH ROW
EXECUTE PROCEDURE public.update_updated_at_column();
```

### 2.2. Konfigurasi Supabase Storage (untuk v3.0+)

Fitur unggah gambar memerlukan konfigurasi Supabase Storage.

1.  Di dashboard Supabase Anda, navigasikan ke **Storage**.
2.  Klik **New Bucket**.
3.  Beri nama bucket `user_images` dan atur sebagai **Public**.
4.  Setelah bucket dibuat, navigasikan ke **Policies**.
5.  Buat kebijakan-kebijakan berikut untuk mengizinkan pengguna mengelola gambar mereka sendiri dengan aman:

    *   **Kebijakan untuk Melihat Gambar:**
        *   Policy Name: `Allow authenticated users to view images`
        *   Allowed operations: `SELECT`
        *   Policy definition: `(bucket_id = 'user_images') AND (auth.role() = 'authenticated')`

    *   **Kebijakan untuk Mengunggah Gambar:**
        *   Policy Name: `Allow users to upload to their own folder`
        *   Allowed operations: `INSERT`
        *   Policy definition: `(bucket_id = 'user_images') AND (auth.uid()::text = (storage.foldername(name))[1])`

    *   **Kebijakan untuk Memperbarui/Menghapus Gambar:**
        *   Policy Name: `Allow users to update/delete their own images`
        *   Allowed operations: `UPDATE`, `DELETE`
        *   Policy definition: `(bucket_id = 'user_images') AND (auth.uid()::text = (storage.foldername(name))[1])`

### 2.3. Migrasi ke v3.0 (Tabel Pengalaman Bersama)

Fitur "Pengalaman Bersama" memerlukan tabel baru. Jalankan skrip SQL berikut:
```sql
CREATE TABLE public.shared_experiences (
    id BIGINT PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    activity_type TEXT NOT NULL, -- 'movie', 'song', etc.
    item_details JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- Kebijakan RLS
ALTER TABLE public.shared_experiences ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can manage their own shared experiences."
ON public.shared_experiences
FOR ALL
USING (auth.uid() = user_id);
```

### 3. Variabel Lingkungan

Buat file `.env` di dalam direktori `backend/` dan isi dengan variabel berikut:

```
MISTRAL_API_KEY="YOUR_MISTRAL_API_KEY"
SUPABASE_URL="YOUR_SUPABASE_PROJECT_URL"
SUPABASE_KEY="YOUR_SUPABASE_ANON_KEY"
PROACTIVE_TRIGGER_SECRET="YOUR_SECRET_KEY_FOR_CRON_JOB"

# Kunci API untuk v3.0+ Tool Use
OPENWEATHER_API_KEY="YOUR_OPENWEATHERMAP_API_KEY"
NEWSAPI_API_KEY="YOUR_NEWSAPI_API_KEY"
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

---

## Konfigurasi Tambahan untuk v2.0

### Menjalankan Fitur Proaktif (Render Cron Job)

Fitur kecerdasan proaktif Astralea (Fase 6) dijalankan oleh tugas terjadwal (cron job) yang memanggil endpoint `/api/trigger_proactive_check`.

Untuk mengkonfigurasi ini di Render:

1.  Buka Dashboard Render Anda dan navigasikan ke layanan Backend Anda.
2.  Pilih menu **Cron Jobs**.
3.  Klik **New Cron Job**.
4.  Isi formulir dengan detail berikut:
    *   **Command**: `curl -X POST https://YOUR_BACKEND_SERVICE_URL.onrender.com/api/trigger_proactive_check -H "X-Trigger-Secret: YOUR_PROACTIVE_TRIGGER_SECRET"`
        *   Ganti `YOUR_BACKEND_SERVICE_URL` dengan URL layanan Render Anda.
        *   Ganti `YOUR_PROACTIVE_TRIGGER_SECRET` dengan kunci rahasia yang Anda tetapkan di variabel lingkungan.
    *   **Schedule**: Pilih jadwal yang Anda inginkan, misalnya `Once a day` (sekali sehari).

Setelah disimpan, Render akan secara otomatis menjalankan perintah ini sesuai jadwal, memicu Astralea untuk memeriksa pengguna yang tidak aktif dan menyiapkan pesan proaktif.
