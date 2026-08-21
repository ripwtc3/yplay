import { useEffect, useState, useRef } from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { toast } from "sonner";
import { EarOff, Send, X } from "lucide-react";
import TimeAgo from "@/components/game/TimeAgo";

/**
 * Whisper panel — 1-to-1 private messages between two alive players.
 * Server delivers only to sender + target, never broadcast.
 */
export default function WhisperPanel({ roomId, currentPhase, me, alivePlayers, onClose }) {
    const { user, addListener } = useAuth();
    const [whispers, setWhispers] = useState([]);
    const [targetId, setTargetId] = useState(null);
    const [msg, setMsg] = useState("");
    const [sending, setSending] = useState(false);
    const scrollRef = useRef(null);

    const load = async () => {
        try {
            const r = await api.get(`/rooms/${roomId}/whispers`);
            setWhispers(r.data.whispers || []);
        } catch (e) { /* ignore */ }
    };

    useEffect(() => { load(); /* eslint-disable-next-line */ }, [roomId]);

    useEffect(() => {
        const off = addListener((m) => {
            if (m.type === "WHISPER_MESSAGE") {
                setWhispers((prev) => [...prev, m.message]);
                if (m.message.sender_user_id !== user?.id) {
                    toast.info(`همس من ${m.message.sender_display_name}`);
                }
            }
        });
        return off;
    }, [addListener, user]);

    useEffect(() => {
        if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }, [whispers.length]);

    const canWhisper = me?.alive && ["DISCUSSION", "VOTING", "NIGHT_RESULT", "VOTE_RESULT"].includes(currentPhase);
    const targets = alivePlayers.filter((p) => p.user_id !== user?.id);

    // Filter whispers by selected conversation partner
    const conversation = targetId
        ? whispers.filter((w) =>
            (w.sender_user_id === user?.id && w.target_user_id === targetId) ||
            (w.sender_user_id === targetId && w.target_user_id === user?.id)
          )
        : whispers;

    const send = async (e) => {
        e?.preventDefault();
        if (!msg.trim() || !targetId || sending) return;
        setSending(true);
        try {
            await api.post(`/rooms/${roomId}/whisper`, { target_user_id: targetId, message: msg.trim() });
            setMsg("");
        } catch (err) {
            toast.error(err.response?.data?.detail || "خطأ");
        } finally { setSending(false); }
    };

    return (
        <div className="rounded-2xl border border-fuchsia-500/30 bg-gradient-to-br from-fuchsia-500/10 via-black/40 to-transparent p-5 mb-6 fade-in-up" data-testid="whisper-panel">
            <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2">
                    <EarOff className="w-5 h-5 text-fuchsia-300" />
                    <h3 className="font-display text-lg font-bold text-fuchsia-200">الهمس السري</h3>
                    <span className="text-[10px] px-2 py-0.5 rounded-full bg-fuchsia-500/20 border border-fuchsia-500/40 text-fuchsia-200 font-body">1-to-1</span>
                </div>
                {onClose && (
                    <button data-testid="close-whisper-btn" onClick={onClose} className="p-1 rounded-lg hover:bg-white/5">
                        <X className="w-4 h-4 text-white/60" />
                    </button>
                )}
            </div>

            {/* Target selector */}
            <div className="mb-3">
                <div className="text-xs text-white/50 font-body mb-2">اختر لاعباً للهمس معه:</div>
                <div className="flex flex-wrap gap-2">
                    <button
                        data-testid="whisper-target-all"
                        onClick={() => setTargetId(null)}
                        className={`text-xs px-3 py-1.5 rounded-full font-body transition-colors ${
                            targetId === null ? "bg-fuchsia-500/30 border border-fuchsia-500/60" : "bg-white/5 border border-white/10 hover:border-white/30"
                        }`}
                    >
                        الكل
                    </button>
                    {targets.map((p) => {
                        const active = targetId === p.user_id;
                        return (
                            <button
                                key={p.user_id}
                                data-testid={`whisper-target-${p.user_id}`}
                                onClick={() => setTargetId(p.user_id)}
                                className={`text-xs px-3 py-1.5 rounded-full font-body transition-colors ${
                                    active ? "bg-fuchsia-500/30 border border-fuchsia-500/60 text-white" : "bg-white/5 border border-white/10 text-white/80 hover:border-white/30"
                                }`}
                            >
                                {p.display_name}
                            </button>
                        );
                    })}
                </div>
            </div>

            {/* Conversation */}
            <div ref={scrollRef} data-testid="whisper-list" className="h-40 overflow-y-auto rounded-lg border border-white/10 bg-black/60 p-3 space-y-2 font-body text-sm mb-3">
                {conversation.length === 0 && (
                    <div className="text-white/30 text-center py-4">
                        {targetId ? "لا رسائل معه بعد — ابدأ همساً" : "لا توجد رسائل خاصة بعد"}
                    </div>
                )}
                {conversation.map((w) => {
                    const mine = w.sender_user_id === user?.id;
                    return (
                        <div key={w.id} data-testid={`whisper-msg-${w.id}`} className="flex flex-col">
                            <div className="flex items-baseline gap-1">
                                <span className={`text-xs font-bold ${mine ? "text-emerald-300" : "text-fuchsia-300"}`}>
                                    {mine ? "أنت" : w.sender_display_name}
                                </span>
                                <span className="text-[10px] text-white/40">←</span>
                                <span className="text-xs font-bold text-white/60">
                                    {mine ? w.target_display_name : "أنت"}
                                </span>
                                <TimeAgo iso={w.created_at} />
                            </div>
                            <div className="text-white/90 whitespace-pre-wrap break-words">{w.message}</div>
                        </div>
                    );
                })}
            </div>

            {canWhisper && targetId ? (
                <form onSubmit={send} className="flex gap-2">
                    <Input
                        data-testid="whisper-input"
                        value={msg}
                        onChange={(e) => setMsg(e.target.value)}
                        placeholder={`اهمس إلى ${targets.find(t => t.user_id === targetId)?.display_name || ""}...`}
                        maxLength={500}
                        className="bg-black/40 border-white/10 h-11"
                    />
                    <Button data-testid="whisper-send-btn" type="submit" disabled={sending || !msg.trim()} className="bg-fuchsia-500 hover:bg-fuchsia-600 h-11 px-4">
                        <Send className="w-4 h-4" />
                    </Button>
                </form>
            ) : !canWhisper ? (
                <div className="text-xs text-white/40 font-body text-center">الهمس متاح أثناء النهار فقط بين الأحياء</div>
            ) : (
                <div className="text-xs text-white/40 font-body text-center">اختر لاعباً لبدء الهمس</div>
            )}
        </div>
    );
}
