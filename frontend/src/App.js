import { useEffect, useState } from "react";
import "@/index.css";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { AuthProvider, useAuth } from "@/context/AuthContext";
import { Toaster } from "sonner";

import Landing from "@/pages/Landing";
import Login from "@/pages/Login";
import Register from "@/pages/Register";
import Dashboard from "@/pages/Dashboard";
import CreateGame from "@/pages/CreateGame";
import JoinRoom from "@/pages/JoinRoom";
import Lobby from "@/pages/Lobby";
import Game from "@/pages/Game";

function Private({ children }) {
    const { user, loading } = useAuth();
    if (loading) return <div className="min-h-screen flex items-center justify-center text-white/60">جاري التحميل...</div>;
    if (!user) return <Navigate to="/login" replace />;
    return children;
}

function App() {
    return (
        <div className="min-h-screen bg-background text-foreground" dir="rtl">
            <AuthProvider>
                <BrowserRouter>
                    <Toaster theme="dark" position="top-center" richColors />
                    <Routes>
                        <Route path="/" element={<Landing />} />
                        <Route path="/login" element={<Login />} />
                        <Route path="/register" element={<Register />} />
                        <Route path="/dashboard" element={<Private><Dashboard /></Private>} />
                        <Route path="/create" element={<Private><CreateGame /></Private>} />
                        <Route path="/join" element={<Private><JoinRoom /></Private>} />
                        <Route path="/room/:roomId" element={<Private><Lobby /></Private>} />
                        <Route path="/game/:roomId" element={<Private><Game /></Private>} />
                    </Routes>
                </BrowserRouter>
            </AuthProvider>
        </div>
    );
}

export default App;
