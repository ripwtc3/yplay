import { useEffect, useState, useRef } from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { toast } from "sonner";
import { MessageCircle, Send, Smile } from "lucide-react";

const REACTIONS = ["👍", "👎", "🤔", "🚨", "🔥", "❤️"];

/**
 * Public chat during Day (DISCUSSION/VOTING). All alive players can post; eliminated watch only.
 * Supports emoji reactions with toggle.
 */
export default function PublicChat({ roomId, currentPhase, me, compact = false }) {
    const { user, addListener } = useAuth();
    const [messages, setMessages] = useState([]);
    const [msg, setMsg] = useState("");
    const [sending, setSending] = useState(false);
    const [openPicker, setOpenPicker] = useState(null); // message_id
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
            } else if (m.type === "MESSAGE_REACTION" && m.channel_type !== "MAFIA") {
                setMessages((prev) => prev.map((msg) =>
                    msg.id === m.message_id ? { ...msg, reactions: m.reactions } : msg
                ));
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

    const react = async (messageId, emoji) => {
        try {
            await api.post(`/rooms/${roomId}/messages/${messageId}/react`, { emoji });
            setOpenPicker(null);
        } catch (err) {
            toast.error(err.response?.data?.detail || "خطأ");
        }
    };

    const listHeight = compact ? "h-72 sm:h-96" : "h-48 sm:h-56";

    return (
        <div className="rounded-2xl border border-white/10 bg-card p-4 sm:p-5 fade-in-up flex flex-col" data-testid="public-chat">
            <div className="flex items-center gap-2 mb-3">
                <MessageCircle className="w-5 h-5 text-yellow-300" />
                <h3 className="font-display text-lg font-bold">نقاش عام</h3>
                {me?.alive === false && <span className="text-[10px] px-2 py-0.5 rounded-full bg-white/10 text-white/60 font-body">مشاهد</span>}
            </div>
            <div
                ref={scrollRef}
                data-testid="public-chat-list"
                className={`${listHeight} overflow-y-auto rounded-lg border border-white/10 bg-black/60 p-3 space-y-3 font-body text-sm flex-1`}
            >
                {messages.length === 0 && (
                    <div className="text-white/30 text-center py-4">ابدأ النقاش — اكتب أفكارك عن Mafia</div>
                )}
                {messages.map((m) => {
                    const mine = m.sender_user_id === user?.id;
                    const reactions = m.reactions || {};
                    const hasReactions = Object.keys(reactions).length > 0;
                    return (
                        <div key={m.id} data-testid={`public-msg-${m.id}`} className="group flex flex-col">
                            <div className={`text-xs font-bold ${mine ? "text-emerald-300" : "text-cyan-300"}`}>
                                {m.sender_display_name}{mine && " (أنت)"}
                            </div>
                            <div className="text-white/90 whitespace-pre-wrap break-words">{m.message}</div>
                            {/* Reactions row */}
                            <div className="flex items-center flex-wrap gap-1 mt-1">
                                {hasReactions && Object.entries(reactions).map(([emoji, users]) => {
                                    const iReacted = users.includes(user?.id);
                                    return (
                                        <button
                                            key={emoji}
                                            data-testid={`reaction-${m.id}-${emoji}`}
                                            onClick={() => react(m.id, emoji)}
                                            className={`inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-full border transition-colors ${
                                                iReacted
                                                    ? "bg-[hsl(355,93%,46%)]/25 border-[hsl(355,93%,46%)]/50 text-white"
                                                    : "bg-white/5 border-white/10 text-white/70 hover:border-white/30"
                                            }`}
                                        >
                                            <span>{emoji}</span>
                                            <span className="font-body">{users.length}</span>
                                        </button>
                                    );
                                })}
                                <div className="relative">
                                    <button
                                        data-testid={`reaction-toggle-${m.id}`}
                                        onClick={() => setOpenPicker(openPicker === m.id ? null : m.id)}
                                        className="text-white/40 hover:text-white/80 text-xs px-1 py-0.5 rounded transition-colors"
                                    >
                                        <Smile className="w-3.5 h-3.5" />
                                    </button>
                                    {openPicker === m.id && (
                                        <div data-testid={`reaction-picker-${m.id}`} className="absolute z-20 mt-1 -ms-1 flex gap-1 bg-black/90 border border-white/15 rounded-lg p-1.5 shadow-2xl">
                                            {REACTIONS.map((e) => (
                                                <button
                                                    key={e}
                                                    data-testid={`pick-reaction-${m.id}-${e}`}
                                                    onClick={() => react(m.id, e)}
                                                    className="text-lg hover:scale-125 transition-transform p-0.5"
                                                >{e}</button>
                                            ))}
                                        </div>
                                    )}
                                </div>
                            </div>
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
