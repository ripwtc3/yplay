import { useEffect, useState, useRef } from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { useTypingIndicator } from "@/lib/useTypingIndicator";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { toast } from "sonner";
import { Skull, MessageSquare, Send, Users, Smile } from "lucide-react";
import TimeAgo from "@/components/game/TimeAgo";

const REACTIONS = ["👍", "👎", "🤔", "🚨", "🔥", "❤️"];

export default function MafiaRoom({ roomId, currentPhase, me }) {
    const { user, addListener, wsSend } = useAuth();
    const [state, setState] = useState(null);
    const [msg, setMsg] = useState("");
    const [sending, setSending] = useState(false);
    const [openPicker, setOpenPicker] = useState(null);
    const scrollRef = useRef(null);
    const { typingUsers, notifyTyping, stopTyping } = useTypingIndicator({ roomId, channel: "MAFIA" });

    const load = async () => {
        try {
            const r = await api.get(`/rooms/${roomId}/mafia-state`);
            setState(r.data);
        } catch (err) {
            setState(null);
        }
    };

    useEffect(() => { load(); /* eslint-disable-next-line */ }, [roomId, currentPhase]);

    useEffect(() => {
        const off = addListener((m) => {
            if (m.type === "MAFIA_MESSAGE") {
                setState((prev) => prev ? { ...prev, messages: [...(prev.messages || []), m.message] } : prev);
            } else if (m.type === "MAFIA_TARGET_VOTE") {
                setState((prev) => {
                    if (!prev) return prev;
                    const votes = [...(prev.current_votes || []).filter(v => v.voter_id !== m.voter_id), { voter_id: m.voter_id, target_id: m.target_id }];
                    return { ...prev, current_votes: votes };
                });
            } else if (m.type === "MESSAGE_REACTION" && m.channel_type === "MAFIA") {
                setState((prev) => {
                    if (!prev) return prev;
                    const messages = (prev.messages || []).map((msg) =>
                        msg.id === m.message_id ? { ...msg, reactions: m.reactions } : msg
                    );
                    return { ...prev, messages };
                });
            }
        });
        return off;
    }, [addListener]);

    useEffect(() => {
        if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }, [state?.messages?.length, typingUsers.length]);

    const onChange = (e) => {
        setMsg(e.target.value);
        if (canAct && e.target.value.trim()) notifyTyping(wsSend);
    };

    const send = async (e) => {
        e?.preventDefault();
        if (!msg.trim() || sending) return;
        setSending(true);
        stopTyping(wsSend);
        try {
            await api.post(`/rooms/${roomId}/mafia-message`, { message: msg.trim() });
            setMsg("");
        } catch (err) {
            toast.error(err.response?.data?.detail || "فشل الإرسال");
        } finally { setSending(false); }
    };

    const vote = async (targetId) => {
        try {
            await api.post(`/rooms/${roomId}/mafia-target-vote`, { target_user_id: targetId });
            setState((prev) => prev ? { ...prev, my_target_vote: targetId } : prev);
            toast.success("تم تسجيل اختيارك");
        } catch (err) {
            toast.error(err.response?.data?.detail || "خطأ");
        }
    };

    const react = async (messageId, emoji) => {
        try {
            await api.post(`/rooms/${roomId}/messages/${messageId}/react`, { emoji });
            setOpenPicker(null);
        } catch (err) {
            toast.error(err.response?.data?.detail || "خطأ");
        }
    };

    if (!state) return null;

    const inMafiaDiscussion = currentPhase === "MAFIA_DISCUSSION";
    const inNightActions = currentPhase === "NIGHT_ACTIONS";
    const canAct = inMafiaDiscussion || inNightActions;
    const isViewer = state.is_viewer;

    const voteCounts = {};
    (state.current_votes || []).forEach((v) => { voteCounts[v.target_id] = (voteCounts[v.target_id] || 0) + 1; });

    const typingLabel = typingUsers.length === 0 ? null
        : typingUsers.length === 1 ? `${typingUsers[0].name} يكتب...`
        : `${typingUsers.length} أعضاء يكتبون...`;

    return (
        <div className="rounded-2xl border-2 border-[hsl(355,93%,46%)]/40 bg-gradient-to-br from-[hsl(355,93%,46%)]/15 via-black/40 to-transparent p-5 mb-6 glow-mafia fade-in-up" data-testid="mafia-private-room">
            <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-2">
                    <Skull className="w-5 h-5 text-[hsl(355,93%,60%)]" />
                    <h3 className="font-display text-xl font-black text-[hsl(355,93%,60%)]">🌙 اجتماع المافيا</h3>
                    {isViewer && <span className="text-[10px] px-2 py-0.5 rounded-full bg-white/10 text-white/60 font-body">مشاهد فقط</span>}
                </div>
                {!isViewer && <span className="text-xs text-white/50 font-body">اتفقوا على الضحية</span>}
            </div>

            <div className="mb-4">
                <div className="text-xs text-white/50 font-body mb-2 flex items-center gap-1"><Users className="w-3 h-3" /> فريق Mafia</div>
                <div className="flex flex-wrap gap-2">
                    {state.teammates.map((t) => (
                        <span
                            key={t.user_id}
                            data-testid={`mafia-teammate-${t.user_id}`}
                            className={`text-xs px-3 py-1.5 rounded-full font-body ${
                                t.alive
                                    ? "bg-[hsl(355,93%,46%)]/20 border border-[hsl(355,93%,46%)]/40 text-white"
                                    : "bg-white/5 border border-white/10 text-white/40 line-through"
                            }`}
                        >
                            {t.display_name}{t.user_id === user?.id && " (أنت)"}
                        </span>
                    ))}
                </div>
            </div>

            <div className="mb-4">
                <div className="text-xs text-white/50 font-body mb-2 flex items-center gap-1"><MessageSquare className="w-3 h-3" /> المحادثة السرية</div>
                <div ref={scrollRef} data-testid="mafia-chat-list" className="h-52 overflow-y-auto rounded-lg border border-white/10 bg-black/60 p-3 space-y-3 font-body text-sm">
                    {(state.messages || []).length === 0 && !typingLabel && (
                        <div className="text-white/30 text-center py-4">لا توجد رسائل بعد — ابدأ النقاش</div>
                    )}
                    {(state.messages || []).map((m) => {
                        const mine = m.sender_user_id === user?.id;
                        const reactions = m.reactions || {};
                        return (
                            <div key={m.id} data-testid={`mafia-msg-${m.id}`} className="flex flex-col">
                                <div className="flex items-baseline">
                                    <span className="text-xs text-[hsl(355,93%,60%)] font-bold">{m.sender_display_name}{mine && " (أنت)"}</span>
                                    <TimeAgo iso={m.created_at} />
                                </div>
                                <div className="text-white/90 whitespace-pre-wrap break-words">{m.message}</div>
                                <div className="flex items-center flex-wrap gap-1 mt-1">
                                    {Object.entries(reactions).map(([emoji, users]) => {
                                        const iReacted = users.includes(user?.id);
                                        return (
                                            <button
                                                key={emoji}
                                                data-testid={`mafia-reaction-${m.id}-${emoji}`}
                                                onClick={() => react(m.id, emoji)}
                                                className={`inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-full border transition-colors ${
                                                    iReacted
                                                        ? "bg-[hsl(355,93%,46%)]/25 border-[hsl(355,93%,46%)]/50 text-white"
                                                        : "bg-white/5 border-white/10 text-white/70 hover:border-white/30"
                                                }`}
                                            >
                                                <span>{emoji}</span><span>{users.length}</span>
                                            </button>
                                        );
                                    })}
                                    {canAct && !isViewer && (
                                        <div className="relative">
                                            <button onClick={() => setOpenPicker(openPicker === m.id ? null : m.id)} className="text-white/40 hover:text-white/80 text-xs px-1 py-0.5">
                                                <Smile className="w-3.5 h-3.5" />
                                            </button>
                                            {openPicker === m.id && (
                                                <div className="absolute z-20 mt-1 -ms-1 flex gap-1 bg-black/90 border border-white/15 rounded-lg p-1.5 shadow-2xl">
                                                    {REACTIONS.map((e) => (
                                                        <button key={e} onClick={() => react(m.id, e)} className="text-lg hover:scale-125 transition-transform p-0.5">{e}</button>
                                                    ))}
                                                </div>
                                            )}
                                        </div>
                                    )}
                                </div>
                            </div>
                        );
                    })}
                    {typingLabel && (
                        <div data-testid="typing-indicator-mafia" className="text-xs text-white/50 italic font-body flex items-center gap-2">
                            <span className="inline-flex gap-0.5">
                                <span className="w-1 h-1 rounded-full bg-[hsl(355,93%,60%)] animate-pulse"></span>
                                <span className="w-1 h-1 rounded-full bg-[hsl(355,93%,60%)] animate-pulse" style={{ animationDelay: "150ms" }}></span>
                                <span className="w-1 h-1 rounded-full bg-[hsl(355,93%,60%)] animate-pulse" style={{ animationDelay: "300ms" }}></span>
                            </span>
                            {typingLabel}
                        </div>
                    )}
                </div>
                {!isViewer && canAct && (
                    <form onSubmit={send} className="mt-2 flex gap-2">
                        <Input data-testid="mafia-msg-input" value={msg} onChange={onChange} placeholder="اكتب رسالتك للفريق..." maxLength={500} className="bg-black/40 border-white/10 h-11" />
                        <Button data-testid="mafia-msg-send-btn" type="submit" disabled={sending || !msg.trim()} className="bg-[hsl(355,93%,46%)] hover:bg-[hsl(355,93%,40%)] h-11 px-4">
                            <Send className="w-4 h-4" />
                        </Button>
                    </form>
                )}
            </div>

            {!isViewer && canAct && me?.alive && (
                <div>
                    <div className="text-xs text-white/50 font-body mb-2">اختر ضحية هذه الليلة</div>
                    <div className="grid sm:grid-cols-2 gap-2">
                        {state.available_targets.map((t) => {
                            const isMine = state.my_target_vote === t.user_id;
                            const count = voteCounts[t.user_id] || 0;
                            return (
                                <button
                                    key={t.user_id}
                                    data-testid={`mafia-target-btn-${t.user_id}`}
                                    onClick={() => vote(t.user_id)}
                                    className={`rounded-lg border p-3 text-right transition-colors font-body flex items-center justify-between ${
                                        isMine ? "border-[hsl(355,93%,46%)] bg-[hsl(355,93%,46%)]/20" : "border-white/10 bg-black/40 hover:border-white/30"
                                    }`}
                                >
                                    <span className="font-bold">{t.display_name}</span>
                                    {count > 0 && <span className="text-xs px-2 py-0.5 rounded-full bg-[hsl(355,93%,46%)]/30 text-[hsl(355,93%,80%)]">{count} صوت</span>}
                                </button>
                            );
                        })}
                    </div>
                    {state.my_target_vote && (
                        <div className="mt-3 text-xs text-emerald-300 font-body">✓ اخترت هدفاً — يمكنك تغييره</div>
                    )}
                </div>
            )}
        </div>
    );
}
