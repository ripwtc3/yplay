import { useEffect, useState, useRef } from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { toast } from "sonner";
import { MessageCircle, Send } from "lucide-react";

/**
 * Public chat during Day (DISCUSSION/VOTING). All alive players can post; eliminated watch only.
 */
export default function PublicChat({ roomId, currentPhase, me }) {
    const { user, addListener } = useAuth();
    const [messages, setMessages] = useState([]);
    const [msg, setMsg] = useState("");
    const [sending, setSending] = useState(false);
    const scrollRef = useRef(null);

    const load = async () => {
        try {
            const r = await api.get(`/rooms/${roomId}/messages`);
            setMessages(r.data.messages || []);
        } catch (e) { /* ignore */ }
    };

    useEffect(() => { load(); /* eslint-disable-next-line */ }, [roomId]);

    useEffect(() => {
        const off = addListener((m) => {
            if (m.type === "PUBLIC_MESSAGE") {
                setMessages((prev) => [...prev, m.message]);
            }
        });
        return off;
    }, [addListener]);

    useEffect(() => {
        if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }, [messages.length]);

    const canSend = me?.alive !== false && ["DISCUSSION", "VOTING", "NIGHT_RESULT", "VOTE_RESULT"].includes(currentPhase);

    const send = async (e) => {
        e?.preventDefault();
        if (!msg.trim() || sending) return;
        setSending(true);
        try {
            await api.post(`/rooms/${roomId}/message`, { message: msg.trim() });
            setMsg("");
        } catch (err) {
            toast.error(err.response?.data?.detail || "فشل الإرسال");
        } finally { setSending(false); }
    };

    return (
        <div className="rounded-2xl border border-white/10 bg-card p-5 mb-6 fade-in-up" data-testid="public-chat">
            <div className="flex items-center gap-2 mb-3">
                <MessageCircle className="w-5 h-5 text-yellow-300" />
                <h3 className="font-display text-lg font-bold">نقاش عام</h3>
                {me?.alive === false && <span className="text-[10px] px-2 py-0.5 rounded-full bg-white/10 text-white/60 font-body">مشاهد</span>}
            </div>
            <div
                ref={scrollRef}
                data-testid="public-chat-list"
                className="h-48 sm:h-56 overflow-y-auto rounded-lg border border-white/10 bg-black/60 p-3 space-y-2 font-body text-sm"
            >
                {messages.length === 0 && (
                    <div className="text-white/30 text-center py-4">ابدأ النقاش — اكتب أفكارك عن Mafia</div>
                )}
                {messages.map((m) => {
                    const mine = m.sender_user_id === user?.id;
                    return (
                        <div key={m.id} data-testid={`public-msg-${m.id}`} className={`flex flex-col ${mine ? "items-start" : "items-start"}`}>
                            <div className={`text-xs font-bold ${mine ? "text-emerald-300" : "text-cyan-300"}`}>
                                {m.sender_display_name}{mine && " (أنت)"}
                            </div>
                            <div className="text-white/90 whitespace-pre-wrap break-words">{m.message}</div>
                        </div>
                    );
                })}
            </div>
            {canSend ? (
                <form onSubmit={send} className="mt-3 flex gap-2">
                    <Input
                        data-testid="public-msg-input"
                        value={msg}
                        onChange={(e) => setMsg(e.target.value)}
                        placeholder="اكتب رسالتك..."
                        maxLength={500}
                        className="bg-black/40 border-white/10 h-11"
                    />
                    <Button data-testid="public-msg-send-btn" type="submit" disabled={sending || !msg.trim()} className="bg-[hsl(355,93%,46%)] hover:bg-[hsl(355,93%,40%)] h-11 px-4">
                        <Send className="w-4 h-4" />
                    </Button>
                </form>
            ) : me?.alive === false ? (
                <div className="mt-3 text-xs text-white/40 font-body text-center">خرجت من اللعبة — يمكنك متابعة النقاش فقط</div>
            ) : (
                <div className="mt-3 text-xs text-white/40 font-body text-center">النقاش متاح فقط أثناء النهار والتصويت</div>
            )}
        </div>
    );
}
