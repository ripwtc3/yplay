import { useEffect, useState, useRef } from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { toast } from "sonner";
import { Skull, MessageSquare, Send, Users } from "lucide-react";

/**
 * Mafia Private Room — only rendered for alive Mafia players (or host if allowed).
 * Fetches /mafia-state initially, then reacts to WebSocket MAFIA_MESSAGE + MAFIA_TARGET_VOTE.
 */
export default function MafiaRoom({ roomId, currentPhase, me }) {
    const { user, addListener } = useAuth();
    const [state, setState] = useState(null);
    const [msg, setMsg] = useState("");
    const [sending, setSending] = useState(false);
    const scrollRef = useRef(null);

    const load = async () => {
        try {
            const r = await api.get(`/rooms/${roomId}/mafia-state`);
            setState(r.data);
        } catch (err) {
            // silently ignore — user might not be authorized (e.g., eliminated mafia)
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
            }
        });
        return off;
    }, [addListener]);

    // Auto-scroll on new messages
    useEffect(() => {
        if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }, [state?.messages?.length]);

    const send = async (e) => {
        e?.preventDefault();
        if (!msg.trim() || sending) return;
        setSending(true);
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

    if (!state) return null;

    const inMafiaDiscussion = currentPhase === "MAFIA_DISCUSSION";
    const inNightActions = currentPhase === "NIGHT_ACTIONS";
    const canAct = inMafiaDiscussion || inNightActions;
    const isViewer = state.is_viewer;

    // count votes on each target for display
    const voteCounts = {};
    (state.current_votes || []).forEach((v) => { voteCounts[v.target_id] = (voteCounts[v.target_id] || 0) + 1; });

    return (
        <div className="rounded-2xl border-2 border-[hsl(355,93%,46%)]/40 bg-gradient-to-br from-[hsl(355,93%,46%)]/15 via-black/40 to-transparent p-5 mb-6 glow-mafia fade-in-up" data-testid="mafia-private-room">
            <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-2">
                    <Skull className="w-5 h-5 text-[hsl(355,93%,60%)]" />
                    <h3 className="font-display text-xl font-black text-[hsl(355,93%,60%)]">🌙 اجتماع المافيا</h3>
                    {isViewer && <span className="text-[10px] px-2 py-0.5 rounded-full bg-white/10 text-white/60 font-body">مشاهد فقط</span>}
                </div>
                {!isViewer && <span className="text-xs text-white/50 font-body">اتفقوا على اللاعب الذي تريدون التخلص منه</span>}
            </div>

            {/* Teammates */}
            <div className="mb-4">
                <div className="text-xs text-white/50 font-body mb-2 flex items-center gap-1">
                    <Users className="w-3 h-3" /> فريق Mafia
                </div>
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

            {/* Chat messages */}
            <div className="mb-4">
                <div className="text-xs text-white/50 font-body mb-2 flex items-center gap-1">
                    <MessageSquare className="w-3 h-3" /> المحادثة السرية
                </div>
                <div
                    ref={scrollRef}
                    data-testid="mafia-chat-list"
                    className="h-52 overflow-y-auto rounded-lg border border-white/10 bg-black/60 p-3 space-y-2 font-body text-sm"
                >
                    {(state.messages || []).length === 0 && (
                        <div className="text-white/30 text-center py-4">لا توجد رسائل بعد — ابدأ النقاش</div>
                    )}
                    {(state.messages || []).map((m) => (
                        <div key={m.id} data-testid={`mafia-msg-${m.id}`} className="flex flex-col">
                            <div className="text-xs text-[hsl(355,93%,60%)] font-bold">{m.sender_display_name}</div>
                            <div className="text-white/90">{m.message}</div>
                        </div>
                    ))}
                </div>
                {!isViewer && canAct && (
                    <form onSubmit={send} className="mt-2 flex gap-2">
                        <Input
                            data-testid="mafia-msg-input"
                            value={msg}
                            onChange={(e) => setMsg(e.target.value)}
                            placeholder="اكتب رسالتك للفريق..."
                            maxLength={500}
                            className="bg-black/40 border-white/10 h-11"
                        />
                        <Button data-testid="mafia-msg-send-btn" type="submit" disabled={sending || !msg.trim()} className="bg-[hsl(355,93%,46%)] hover:bg-[hsl(355,93%,40%)] h-11 px-4">
                            <Send className="w-4 h-4" />
                        </Button>
                    </form>
                )}
            </div>

            {/* Target voting */}
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
                                        isMine
                                            ? "border-[hsl(355,93%,46%)] bg-[hsl(355,93%,46%)]/20"
                                            : "border-white/10 bg-black/40 hover:border-white/30"
                                    }`}
                                >
                                    <span className="font-bold">{t.display_name}</span>
                                    {count > 0 && (
                                        <span className="text-xs px-2 py-0.5 rounded-full bg-[hsl(355,93%,46%)]/30 text-[hsl(355,93%,80%)]">
                                            {count} صوت
                                        </span>
                                    )}
                                </button>
                            );
                        })}
                    </div>
                    {state.my_target_vote && (
                        <div className="mt-3 text-xs text-emerald-300 font-body">✓ اخترت هدفاً — يمكنك تغييره خلال الوقت المتبقي</div>
                    )}
                </div>
            )}
        </div>
    );
}
