"use client";

import { useState, FormEvent, useEffect, useRef } from "react";
import { createClientComponentClient } from '@supabase/auth-helpers-nextjs';
import { Session, SupabaseClient } from '@supabase/supabase-js';
import AuthForm from './auth';
import type { Database } from './database.types';

// Tipe untuk pesan dalam obrolan
interface Message {
  sender: "user" | "ai";
  text: string;
}

// Komponen Antarmuka Obrolan
function ChatInterface({ session, supabase }: { session: Session; supabase: SupabaseClient<Database> }) {
  const [inputMessage, setInputMessage] = useState("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [chemistryScore, setChemistryScore] = useState(0); // Dimulai dari 0, akan diperbarui dari API
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });

  useEffect(() => { scrollToBottom(); }, [messages]);

  // Ambil skor awal saat komponen dimuat
  useEffect(() => {
    const fetchInitialScore = async () => {
        const { data, error } = await supabase
            .from('profiles')
            .select('chemistry_score')
            .eq('id', session.user.id)
            .single();
        if (data) setChemistryScore(data.chemistry_score ?? 0);
    };
    fetchInitialScore();
  }, [session.user.id, supabase]);

  const handleSignOut = async () => {
    await supabase.auth.signOut();
    window.location.reload();
  };

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!inputMessage.trim() || isLoading) return;

    const userMessage: Message = { sender: "user", text: inputMessage };
    setMessages((prev) => [...prev, userMessage]);
    setInputMessage("");
    setIsLoading(true);

    try {
      const response = await fetch("http://127.0.0.1:8000/api/chat", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Authorization": `Bearer ${session.access_token}`,
        },
        body: JSON.stringify({ message: inputMessage }),
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
      <header className="bg-white shadow-sm p-4 flex justify-between items-center border-b">
        <div>
          <h1 className="text-2xl font-bold text-gray-800">Astralea</h1>
          <p className="text-xs text-gray-500">Logged in as: {session.user.email}</p>
        </div>
        <div className="flex items-center space-x-4">
            <div className="text-lg text-right">
                <span className="font-semibold text-gray-600">Chemistry: </span>
                <span className="font-mono bg-blue-100 text-blue-800 py-1 px-2 rounded">{chemistryScore}</span>
            </div>
            <button onClick={handleSignOut} className="px-3 py-2 text-sm bg-red-500 text-white rounded-lg hover:bg-red-600">Sign Out</button>
        </div>
      </header>

      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.map((msg, index) => (
          <div key={index} className={`flex ${msg.sender === "user" ? "justify-end" : "justify-start"}`}>
            <div className={`max-w-sm lg:max-w-md p-3 rounded-xl shadow-sm ${msg.sender === "user" ? "bg-blue-500 text-white" : "bg-white text-gray-800"}`}>
              <p style={{whiteSpace: 'pre-wrap'}}>{msg.text}</p>
            </div>
          </div>
        ))}
        {isLoading && <div className="flex justify-start"><div className="max-w-xs p-3 rounded-xl bg-white text-gray-500 shadow-sm"><span className="animate-pulse">Thinking...</span></div></div>}
        <div ref={messagesEndRef} />
      </div>

      <footer className="bg-white p-4 border-t">
        <form onSubmit={handleSubmit} className="flex space-x-3">
          <input type="text" value={inputMessage} onChange={(e) => setInputMessage(e.target.value)} placeholder="Type your message..." className="flex-1 p-3 border rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500" disabled={isLoading} autoFocus/>
          <button type="submit" className="px-6 py-3 bg-blue-500 text-white font-semibold rounded-xl hover:bg-blue-600 disabled:bg-blue-300" disabled={isLoading || !inputMessage.trim()}>Send</button>
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
