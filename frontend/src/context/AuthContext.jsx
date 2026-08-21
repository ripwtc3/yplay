import React, { createContext, useContext, useEffect, useState, useRef, useCallback } from "react";
import { api, wsUrl } from "@/lib/api";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
    const [user, setUser] = useState(null);
    const [loading, setLoading] = useState(true);
    const [wsReady, setWsReady] = useState(false);
    const wsRef = useRef(null);
    const listenersRef = useRef(new Set());
    const roomIdRef = useRef(null);

    // Load user from token
    useEffect(() => {
        const token = localStorage.getItem("token");
        if (!token) { setLoading(false); return; }
        api.get("/auth/me")
            .then((res) => setUser(res.data))
            .catch(() => localStorage.removeItem("token"))
            .finally(() => setLoading(false));
    }, []);

    // Setup WS whenever user is set
    useEffect(() => {
        if (!user) {
            if (wsRef.current) { wsRef.current.close(); wsRef.current = null; }
            setWsReady(false);
            return;
        }
        const token = localStorage.getItem("token");
        if (!token) return;
        const ws = new WebSocket(wsUrl(token));
        wsRef.current = ws;
        ws.onopen = () => {
            setWsReady(true);
            if (roomIdRef.current) {
                ws.send(JSON.stringify({ type: "SUBSCRIBE_ROOM", room_id: roomIdRef.current }));
            }
        };
        ws.onmessage = (ev) => {
            try {
                const data = JSON.parse(ev.data);
                listenersRef.current.forEach((cb) => cb(data));
            } catch (e) { /* ignore */ }
        };
        ws.onclose = () => setWsReady(false);
        ws.onerror = () => setWsReady(false);
        return () => { ws.close(); };
    }, [user]);

    const addListener = useCallback((cb) => {
        listenersRef.current.add(cb);
        return () => listenersRef.current.delete(cb);
    }, []);

    const subscribeRoom = useCallback((roomId) => {
        roomIdRef.current = roomId;
        if (wsRef.current && wsRef.current.readyState === 1) {
            wsRef.current.send(JSON.stringify({ type: "SUBSCRIBE_ROOM", room_id: roomId }));
        }
    }, []);

    const wsSend = useCallback((payload) => {
        if (wsRef.current && wsRef.current.readyState === 1) {
            wsRef.current.send(JSON.stringify(payload));
        }
    }, []);

    const login = async (email, password) => {
        const res = await api.post("/auth/login", { email, password });
        localStorage.setItem("token", res.data.token);
        setUser(res.data.user);
        return res.data.user;
    };

    const register = async (payload) => {
        const res = await api.post("/auth/register", payload);
        localStorage.setItem("token", res.data.token);
        setUser(res.data.user);
        return res.data.user;
    };

    const logout = () => {
        localStorage.removeItem("token");
        setUser(null);
        roomIdRef.current = null;
        if (wsRef.current) wsRef.current.close();
    };

    return (
        <AuthContext.Provider value={{ user, loading, login, register, logout, addListener, subscribeRoom, wsSend, wsReady }}>
            {children}
        </AuthContext.Provider>
    );
}

export const useAuth = () => useContext(AuthContext);
