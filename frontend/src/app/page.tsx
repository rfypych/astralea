"use client";

import { useState, FormEvent, useEffect, useRef } from "react";
import { createClientComponentClient } from '@supabase/auth-helpers-nextjs';
import { Session, SupabaseClient } from '@supabase/supabase-js';
import AuthForm from './auth';
import type { Database } from './database.types';

import { v4 as uuidv4 } from 'uuid';

// Tipe pesan diperbarui untuk mendukung gambar
interface Message {
  sender: "user" | "ai";
  text: string;
  imageUrl?: string;
}

// Komponen Antarmuka Obrolan
function ChatInterface({ session, supabase }: { session: Session; supabase: SupabaseClient<Database> }) {
  const [inputMessage, setInputMessage] = useState("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [chemistryScore, setChemistryScore] = useState(0);
  const [isLoading, setIsLoading] = useState(false);
  const [imageFile, setImageFile] = useState<File | null>(null);
  const [imagePreview, setImagePreview] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  useEffect(() => { scrollToBottom(); }, [messages]);

  // Efek untuk mengambil data awal
  useEffect(() => {
    const fetchInitialData = async () => {
      // ... (logika fetch data awal tetap sama)
    };
    fetchInitialData();
  }, [session.user.id, session.access_token, supabase]);

  const handleSignOut = async () => { /* ... (tetap sama) ... */ };

  const handleImageChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const file = e.target.files[0];
      setImageFile(file);
      setImagePreview(URL.createObjectURL(file));
    }
  };

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if ((!inputMessage.trim() && !imageFile) || isLoading) return;

    setIsLoading(true);
    let uploadedImageUrl: string | undefined = undefined;

    // 1. Unggah gambar jika ada
    if (imageFile) {
      const fileName = `${session.user.id}/${uuidv4()}`;
      const { data, error } = await supabase.storage
        .from('user_images') // Nama bucket Anda di Supabase
        .upload(fileName, imageFile);

      if (error) {
        console.error("Error uploading image:", error);
        // Tampilkan pesan error kepada pengguna
        setIsLoading(false);
        return;
      }

      const { data: { publicUrl } } = supabase.storage
        .from('user_images')
        .getPublicUrl(fileName);
      uploadedImageUrl = publicUrl;
    }

    // 2. Tambahkan pesan pengguna ke UI
    const userMessage: Message = { sender: "user", text: inputMessage, imageUrl: imagePreview ?? undefined };
    setMessages((prev) => [...prev, userMessage]);
    setInputMessage("");
    setImageFile(null);
    setImagePreview(null);

    // 3. Kirim ke backend
    try {
      const response = await fetch("http://127.0.0.1:8000/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json", "Authorization": `Bearer ${session.access_token}` },
        body: JSON.stringify({ message: inputMessage, image_url: uploadedImageUrl }),
      });

      if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
      const data = await response.json();
      const aiMessage: Message = { sender: "ai", text: data.response };
      setMessages((prev) => [...prev, aiMessage]);
      setChemistryScore(data.chemistry_score);
    } catch (error) {
      console.error("Error fetching AI response:", error);
      const errorMessage: Message = { sender: "ai", text: "Sorry, an error occurred." };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <main className="flex flex-col h-screen bg-gray-50">
      <header>
        {/* ... (header tetap sama) ... */}
      </header>

      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.map((msg, index) => (
          <div key={index} className={`flex ${msg.sender === "user" ? "justify-end" : "justify-start"}`}>
            <div className={`max-w-sm lg:max-w-md p-3 rounded-xl shadow-sm ${msg.sender === "user" ? "bg-blue-500 text-white" : "bg-white text-gray-800"}`}>
              {msg.imageUrl && <img src={msg.imageUrl} alt="User upload" className="rounded-lg mb-2 max-h-60" />}
              {msg.text && <p style={{whiteSpace: 'pre-wrap'}}>{msg.text}</p>}
            </div>
          </div>
        ))}
        {/* ... (indikator loading tetap sama) ... */}
        <div ref={messagesEndRef} />
      </div>

      <footer className="bg-white p-4 border-t">
        {imagePreview && (
          <div className="relative w-24 h-24 mb-2">
            <img src={imagePreview} alt="Preview" className="w-full h-full object-cover rounded-lg"/>
            <button onClick={() => { setImageFile(null); setImagePreview(null); }} className="absolute top-0 right-0 bg-red-500 text-white rounded-full w-6 h-6 flex items-center justify-center text-xs">&times;</button>
          </div>
        )}
        <form onSubmit={handleSubmit} className="flex space-x-3">
          <input type="file" ref={fileInputRef} onChange={handleImageChange} accept="image/*" className="hidden"/>
          <button type="button" onClick={() => fileInputRef.current?.click()} className="p-3 border rounded-xl hover:bg-gray-100">🖼️</button>
          <input type="text" value={inputMessage} onChange={(e) => setInputMessage(e.target.value)} placeholder="Type your message or upload an image..." className="flex-1 p-3 border rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500" disabled={isLoading} autoFocus/>
          <button type="submit" className="px-6 py-3 bg-blue-500 text-white font-semibold rounded-xl hover:bg-blue-600 disabled:bg-blue-300" disabled={isLoading || (!inputMessage.trim() && !imageFile)}>Send</button>
        </form>
      </footer>
    </main>
  );
}

// Komponen Halaman Utama untuk mengelola sesi
export default function Home() {
  const [session, setSession] = useState<Session | null>(null);
  const supabase = createClientComponentClient<Database>();

  useEffect(() => {
    const getSession = async () => {
      const { data: { session } } = await supabase.auth.getSession();
      setSession(session);
    };
    getSession();

    const { data: { subscription } } = supabase.auth.onAuthStateChange((_event, session) => {
      setSession(session);
    });

    return () => subscription.unsubscribe();
  }, [supabase.auth]);

  if (!session) {
    return <AuthForm />;
  }

  return <ChatInterface session={session} supabase={supabase} />;
}
