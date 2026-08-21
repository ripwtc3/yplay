import { useEffect, useRef, useState, useCallback } from "react";
import { useAuth } from "@/context/AuthContext";

/**
 * Hook: returns { typingUsers: [display_name], notifyTyping(text) } for a given channel
 * - Broadcasts TYPING_START via WS on input change, and TYPING_STOP after 3s idle
 * - Listens for TYPING_START/TYPING_STOP from others in the same channel
 */
export function useTypingIndicator({ roomId, channel = "PUBLIC" }) {
    const { user, addListener } = useAuth();
    const [typingUsers, setTypingUsers] = useState({}); // {user_id: {name, expires_at}}
    const timerRef = useRef(null);
    const wsRef = useRef(null);
    const lastSentRef = useRef(0);

    // grab ws ref lazily from AuthContext internals via window (fallback) - simpler: use a small effect that finds ws through addListener setup
    // Instead, we'll POST via the auth-context's ws by exposing helper. Simpler approach: create a helper that opens its own send.
    // BUT easier: augment AuthContext later. For now, we require the caller to give ws via prop.

    useEffect(() => {
        const off = addListener((m) => {
            if ((m.type === "TYPING_START" || m.type === "TYPING_STOP") && m.channel === channel) {
                if (m.user_id === user?.id) return; // ignore self
                setTypingUsers((prev) => {
                    const next = { ...prev };
                    if (m.type === "TYPING_START") {
                        next[m.user_id] = { name: m.display_name || "لاعب", expires_at: Date.now() + 4000 };
                    } else {
                        delete next[m.user_id];
                    }
                    return next;
                });
            }
        });
        return off;
    }, [addListener, channel, user]);

    // expire stale entries every 1s
    useEffect(() => {
        const t = setInterval(() => {
            setTypingUsers((prev) => {
                const now = Date.now();
                const next = {};
                for (const [k, v] of Object.entries(prev)) {
                    if (v.expires_at > now) next[k] = v;
                }
                return next;
            });
        }, 1000);
        return () => clearInterval(t);
    }, []);

    const notifyTyping = useCallback((sendFn) => {
        const now = Date.now();
        if (now - lastSentRef.current > 1500) {
            lastSentRef.current = now;
            sendFn({ type: "TYPING_START", room_id: roomId, channel });
        }
        if (timerRef.current) clearTimeout(timerRef.current);
        timerRef.current = setTimeout(() => {
            sendFn({ type: "TYPING_STOP", room_id: roomId, channel });
            lastSentRef.current = 0;
        }, 2500);
    }, [roomId, channel]);

    const stopTyping = useCallback((sendFn) => {
        if (timerRef.current) clearTimeout(timerRef.current);
        if (lastSentRef.current) {
            sendFn({ type: "TYPING_STOP", room_id: roomId, channel });
            lastSentRef.current = 0;
        }
    }, [roomId, channel]);

    return {
        typingUsers: Object.values(typingUsers),
        notifyTyping,
        stopTyping,
    };
}
