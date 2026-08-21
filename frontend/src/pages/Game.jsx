import { useEffect, useState, useMemo } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import { Skull, Stethoscope, Search, User, Moon, Sun, Vote, Trophy, Home, Eye, EyeOff } from "lucide-react";
import MafiaRoom from "@/components/game/MafiaRoom";
import PublicChat from "@/components/game/PublicChat";

const ROLE_META = {
    MAFIA: { label: "Mafia", icon: Skull, color: "hsl(355,93%,60%)", bg: "from-[hsl(355,93%,46%)]/20", glow: "glow-mafia", desc: "هدفك القضاء على المواطنين" },
    DOCTOR: { label: "Doctor", icon: Stethoscope, color: "rgb(52,211,153)", bg: "from-emerald-500/20", glow: "glow-doctor", desc: "احمِ لاعباً كل ليلة" },
    DETECTIVE: { label: "Detective", icon: Search, color: "rgb(34,211,238)", bg: "from-cyan-500/20", glow: "glow-detective", desc: "حقق مع لاعب لتعرف إن كان Mafia" },
    CITIZEN: { label: "Citizen", icon: User, color: "rgb(226,232,240)", bg: "from-white/10", glow: "glow-citizen", desc: "اكشف Mafia بالنقاش والتصويت" },
};

function Countdown({ endsAt }) {
    const [now, setNow] = useState(Date.now() / 1000);
    useEffect(() => {
        const t = setInterval(() => setNow(Date.now() / 1000), 250);
        return () => clearInterval(t);
    }, []);
    if (!endsAt) return <span>--</span>;
    const end = new Date(endsAt).getTime() / 1000;
    const remaining = Math.max(0, Math.floor(end - now));
    const critical = remaining <= 10;
    return <span className={critical ? "text-[hsl(355,93%,60%)] animate-pulse" : ""}>{remaining}s</span>;
}

const PHASE_LABELS = {
    ROLE_ASSIGNMENT: "توزيع الأدوار...",
    MAFIA_DISCUSSION: "اجتماع المافيا",
    NIGHT_ACTIONS: "حركات الليل",
    NIGHT_RESULT: "نتيجة الليل",
    DISCUSSION: "النقاش",
    VOTING: "التصويت",
    VOTE_RESULT: "نتيجة التصويت",
};

export default function Game() {
    const { roomId } = useParams();
    const nav = useNavigate();
    const { user, addListener, subscribeRoom, wsReady } = useAuth();
    const [state, setState] = useState(null);
    const [busy, setBusy] = useState(false);
    const [investigation, setInvestigation] = useState(null);
    const [showRole, setShowRole] = useState(true);

    const load = async () => {
        try {
            const r = await api.get(`/rooms/${roomId}/state`);
            setState(r.data);
        } catch (err) {
            toast.error(err.response?.data?.detail || "خطأ");
            nav("/dashboard");
        }
    };

    useEffect(() => { load(); /* eslint-disable-next-line */ }, [roomId]);
    useEffect(() => { if (wsReady) subscribeRoom(roomId); }, [wsReady, roomId, subscribeRoom]);

    useEffect(() => {
        const off = addListener((msg) => {
            if (["PHASE_STARTED", "NIGHT_RESULT", "VOTE_RESULT", "GAME_OVER", "GAME_STARTED", "NIGHT_ACTION_CONFIRMED", "VOTE_SUBMITTED"].includes(msg.type)) {
                load();
                if (msg.type === "NIGHT_RESULT") {
                    if (msg.eliminated) toast.warning(`تم إخراج ${msg.eliminated.display_name} هذه الليلة`);
                    else toast.info("لم يتم إخراج أي لاعب هذه الليلة");
                }
                if (msg.type === "VOTE_RESULT") {
                    if (msg.eliminated) toast.warning(`تم إقصاء ${msg.eliminated.display_name} بالتصويت`);
                    else toast.info("تعادل — لم يتم إقصاء أحد");
                }
                if (msg.type === "GAME_OVER") toast.success(msg.winner === "MAFIA" ? "فوز Mafia" : "فوز المواطنين");
            } else if (msg.type === "INVESTIGATION_RESULT") {
                setInvestigation(msg);
                toast.success(`${msg.target_name}: ${msg.result === "MAFIA" ? "MAFIA ✗" : "مواطن ✓"}`);
            } else if (msg.type === "PLAYER_ONLINE" || msg.type === "PLAYER_OFFLINE") {
                load();
            }
        });
        return off;
    }, [addListener]);

    const submitNight = async (targetId) => {
        setBusy(true);
        try {
            const map = { DOCTOR: "PROTECT", DETECTIVE: "INVESTIGATE" };
            await api.post(`/rooms/${roomId}/night-action`, { action_type: map[state.me.role], target_user_id: targetId });
        } catch (err) {
            toast.error(err.response?.data?.detail || "خطأ");
        } finally { setBusy(false); }
    };

    const submitVote = async (targetId) => {
        setBusy(true);
        try {
            await api.post(`/rooms/${roomId}/vote`, { target_user_id: targetId });
        } catch (err) {
            toast.error(err.response?.data?.detail || "خطأ");
        } finally { setBusy(false); }
    };

    const alivePlayers = useMemo(
        () => state?.session?.players?.filter((p) => p.alive) || [],
        [state]
    );

    if (!state) return <div className="min-h-screen grid place-items-center text-white/60 font-body">جاري التحميل...</div>;

    const phase = state.session?.current_phase;
    const roundNum = state.session?.round_number || 0;
    const me = state.me || {};
    const meta = ROLE_META[me.role] || ROLE_META.CITIZEN;
    const RoleIcon = meta.icon;
    const isMafia = me.role === "MAFIA";
    const isNight = ["MAFIA_DISCUSSION", "NIGHT_ACTIONS", "NIGHT_RESULT", "ROLE_ASSIGNMENT"].includes(phase);
    const hostCanViewMafia = state.room?.settings?.host_can_view_mafia_chat && user?.id === state.room?.host_id;

    // GAME OVER
    if (phase === "GAME_OVER") {
        const winner = state.session.winner;
        return (
            <div className="min-h-screen noise-bg">
                <div className="max-w-4xl mx-auto px-6 py-16 text-center fade-in-up">
                    <Trophy className={`w-20 h-20 mx-auto mb-6 ${winner === "MAFIA" ? "text-[hsl(355,93%,60%)]" : "text-emerald-400"}`} />
                    <h1 className="font-display text-5xl sm:text-6xl font-black">
                        {winner === "MAFIA" ? "فوز Mafia" : "فوز المواطنين"}
                    </h1>
                    <p className="mt-4 text-white/60 font-body">انتهت اللعبة بعد {roundNum} جولة</p>
                    <div className="mt-10 grid sm:grid-cols-2 md:grid-cols-3 gap-3 text-right">
                        {state.session.players.map((p) => {
                            const m = ROLE_META[p.role];
                            const I = m.icon;
                            return (
                                <div key={p.user_id} data-testid={`gameover-player-${p.user_id}`} className={`rounded-xl border border-white/10 p-4 ${!p.alive ? "opacity-60" : ""} bg-card`}>
                                    <div className="flex items-center gap-2">
                                        <I className="w-4 h-4" style={{ color: m.color }} />
                                        <span className="font-display font-bold">{m.label}</span>
                                    </div>
                                    <div className={`mt-2 font-body ${!p.alive ? "line-through text-white/50" : ""}`}>{p.display_name}</div>
                                </div>
                            );
                        })}
                    </div>
                    <Button data-testid="back-home-btn" onClick={() => nav("/dashboard")} className="mt-10 h-14 px-8 bg-[hsl(355,93%,46%)] hover:bg-[hsl(355,93%,40%)] font-display font-bold">
                        <Home className="w-5 h-5 ms-2" /> عودة للوحة
                    </Button>
                </div>
            </div>
        );
    }

    const bgClass = isNight ? "bg-[hsl(240,10%,3%)]" : "bg-[hsl(240,10%,8%)]";

    return (
        <div className={`min-h-screen transition-colors ${bgClass}`}>
            <div className="sticky top-0 z-40 backdrop-blur-xl bg-black/60 border-b border-white/10">
                <div className="max-w-5xl mx-auto px-6 py-4 flex items-center justify-between">
                    <div className="flex items-center gap-3">
                        {isNight ? <Moon className="w-6 h-6 text-cyan-300" /> : <Sun className="w-6 h-6 text-yellow-300" />}
                        <div>
                            <div className="font-display font-bold text-lg" data-testid="phase-name">
                                {PHASE_LABELS[phase] || phase}
                            </div>
                            <div className="text-xs text-white/50 font-body">الجولة {roundNum}</div>
                        </div>
                    </div>
                    <div className="font-display font-black text-3xl" data-testid="phase-timer">
                        <Countdown endsAt={state.session?.phase_ends_at} />
                    </div>
                </div>
            </div>

            <div className="max-w-5xl mx-auto px-6 py-8">
                {/* Role banner */}
                {me.role && (
                    <div className={`rounded-2xl border border-white/10 bg-gradient-to-br ${meta.bg} to-transparent p-5 mb-6 ${meta.glow}`}>
                        <div className="flex items-center justify-between gap-4">
                            <div className="flex items-center gap-3">
                                <RoleIcon className="w-8 h-8" style={{ color: meta.color }} />
                                <div>
                                    <div className="text-white/60 text-xs font-body">دورك السري</div>
                                    <div className="font-display text-2xl font-black" style={{ color: meta.color }} data-testid="my-role-label">
                                        {showRole ? meta.label : "•••••"}
                                    </div>
                                    <div className="text-white/60 text-sm font-body mt-1">{showRole && meta.desc}</div>
                                </div>
                            </div>
                            <button data-testid="toggle-role-btn" onClick={() => setShowRole((s) => !s)} className="p-2 rounded-lg border border-white/10 hover:bg-white/5 transition-colors">
                                {showRole ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                            </button>
                        </div>
                        {me.role === "MAFIA" && me.mafia_partners?.length > 0 && (
                            <div className="mt-3 text-sm text-white/70 font-body">شركاؤك: {me.mafia_partners.map((p) => p.display_name).join("، ")}</div>
                        )}
                        {!me.alive && <div className="mt-3 text-sm text-red-400 font-body">أنت خارج اللعبة — تستطيع المشاهدة فقط</div>}
                    </div>
                )}

                {/* ROLE_ASSIGNMENT */}
                {phase === "ROLE_ASSIGNMENT" && (
                    <div className="text-center py-16 font-body text-white/60 fade-in-up">
                        <div className="animate-pulse text-2xl font-display font-bold">توزيع الأدوار سراً...</div>
                    </div>
                )}

                {/* MAFIA private room */}
                {(phase === "MAFIA_DISCUSSION" || phase === "NIGHT_ACTIONS" || phase === "NIGHT_RESULT") && (isMafia || hostCanViewMafia) && me.alive !== false && (
                    <MafiaRoom roomId={roomId} currentPhase={phase} me={me} />
                )}

                {/* Non-mafia messages during night */}
                {phase === "MAFIA_DISCUSSION" && !isMafia && !hostCanViewMafia && (
                    <div className="rounded-xl border border-white/10 bg-card p-6 text-center font-body text-white/70 mb-6">
                        <Moon className="w-8 h-8 mx-auto mb-3 text-cyan-300" />
                        <div className="font-display text-xl font-bold">الليل مستمر...</div>
                        <div className="text-sm text-white/50 mt-1">انتظر دورك — Mafia تتشاور</div>
                    </div>
                )}

                {/* NIGHT_ACTIONS: role-specific for Doctor/Detective */}
                {phase === "NIGHT_ACTIONS" && me.alive && (me.role === "DOCTOR" || me.role === "DETECTIVE") && (
                    <NightAction me={me} alivePlayers={alivePlayers.filter(p => p.user_id !== user.id)} onSubmit={submitNight} busy={busy} />
                )}
                {phase === "NIGHT_ACTIONS" && me.role === "CITIZEN" && me.alive && (
                    <div className="rounded-xl border border-white/10 bg-card p-6 text-center font-body text-white/70 mb-6">
                        🌙 ليس لديك حركة ليلية — انتظر بداية النهار
                    </div>
                )}
                {phase === "NIGHT_ACTIONS" && !me.alive && (
                    <div className="rounded-xl border border-white/10 bg-card p-6 text-center text-white/60 font-body">🌙 الليل — أنت مشاهد فقط</div>
                )}

                {/* Result / Discussion */}
                {(phase === "NIGHT_RESULT" || phase === "VOTE_RESULT" || phase === "DISCUSSION") && (
                    <div className="rounded-xl border border-white/10 bg-card p-6 mb-6 text-center font-body">
                        {phase === "DISCUSSION" && <div className="font-display text-xl font-bold">☀️ ناقشوا واكشفوا Mafia</div>}
                        {phase === "NIGHT_RESULT" && <div className="font-display text-xl font-bold">📜 عرض نتيجة الليل...</div>}
                        {phase === "VOTE_RESULT" && <div className="font-display text-xl font-bold">📜 عرض نتيجة التصويت...</div>}
                    </div>
                )}

                {/* Public chat during day */}
                {["DISCUSSION", "VOTING", "NIGHT_RESULT", "VOTE_RESULT"].includes(phase) && (
                    <PublicChat roomId={roomId} currentPhase={phase} me={me} />
                )}

                {/* VOTING */}
                {phase === "VOTING" && me.alive && !me.vote && (
                    <div className="mb-6 fade-in-up">
                        <div className="flex items-center gap-2 mb-4">
                            <Vote className="w-5 h-5 text-[hsl(355,93%,60%)]" />
                            <h3 className="font-display text-xl font-bold">اختر لاعباً للإقصاء</h3>
                        </div>
                        <div className="grid sm:grid-cols-2 gap-3">
                            {alivePlayers.filter(p => p.user_id !== user.id).map((p) => (
                                <button
                                    key={p.user_id}
                                    data-testid={`vote-btn-${p.user_id}`}
                                    disabled={busy}
                                    onClick={() => submitVote(p.user_id)}
                                    className="rounded-xl border border-white/10 bg-card p-4 hover:border-[hsl(355,93%,46%)] hover:bg-[hsl(355,93%,46%)]/10 transition-colors text-right"
                                >
                                    <div className="font-display font-bold text-lg">{p.display_name}</div>
                                    <div className="text-xs text-white/50 font-body">@{p.username}</div>
                                </button>
                            ))}
                        </div>
                    </div>
                )}
                {phase === "VOTING" && me.vote && (
                    <div className="rounded-xl border border-emerald-500/30 bg-emerald-500/10 p-4 mb-6 font-body text-emerald-300 text-center">
                        ✓ تم تسجيل تصويتك — بانتظار الباقين
                    </div>
                )}

                {investigation && me.role === "DETECTIVE" && (
                    <div className="rounded-xl border border-cyan-500/30 bg-cyan-500/10 p-4 mb-6 font-body">
                        <div className="text-cyan-300 font-display font-bold mb-1">تحقيقك (جولة {investigation.round_number})</div>
                        <div>{investigation.target_name}: {investigation.result === "MAFIA" ? "🚨 MAFIA" : "✓ ليس Mafia"}</div>
                    </div>
                )}

                {/* All players */}
                <div>
                    <h4 className="font-display font-bold mb-3 text-white/70">اللاعبون</h4>
                    <div className="grid sm:grid-cols-2 md:grid-cols-3 gap-3">
                        {state.session?.players?.map((p) => (
                            <div
                                key={p.user_id}
                                data-testid={`game-player-${p.user_id}`}
                                className={`rounded-xl border p-3 flex items-center gap-3 ${p.alive ? "border-white/10 bg-card" : "border-white/5 bg-black/40 opacity-60"}`}
                            >
                                <div className="w-9 h-9 rounded-full bg-gradient-to-br from-[hsl(355,93%,46%)]/40 to-black grid place-items-center font-display font-bold text-sm">
                                    {p.display_name?.[0] || "?"}
                                </div>
                                <div className="flex-1 min-w-0">
                                    <div className={`font-body font-bold truncate ${!p.alive ? "line-through" : ""}`}>{p.display_name}</div>
                                    <div className="text-xs text-white/50 font-body">
                                        {p.alive ? (p.connection_status === "ONLINE" ? "متصل" : "غير متصل") : "خارج اللعبة"}
                                    </div>
                                </div>
                                {!p.alive && <Skull className="w-4 h-4 text-white/30" />}
                            </div>
                        ))}
                    </div>
                </div>
            </div>
        </div>
    );
}

function NightAction({ me, alivePlayers, onSubmit, busy }) {
    const [selected, setSelected] = useState(null);
    const meta = ROLE_META[me.role];
    const already = !!me.night_action;
    const label = { DOCTOR: "اختر لاعباً لحمايته", DETECTIVE: "اختر لاعباً للتحقيق معه" }[me.role];

    if (already) {
        return (
            <div className="rounded-xl border border-emerald-500/30 bg-emerald-500/10 p-4 font-body text-emerald-300 text-center mb-6">
                ✓ تم تسجيل حركتك الليلية
            </div>
        );
    }

    return (
        <div className="fade-in-up mb-6">
            <div className="flex items-center gap-2 mb-4">
                <meta.icon className="w-5 h-5" style={{ color: meta.color }} />
                <h3 className="font-display text-xl font-bold">{label}</h3>
            </div>
            <div className="grid sm:grid-cols-2 gap-3 mb-4">
                {alivePlayers.map((p) => (
                    <button
                        key={p.user_id}
                        data-testid={`night-target-${p.user_id}`}
                        onClick={() => setSelected(p.user_id)}
                        className={`rounded-xl border p-4 text-right transition-colors ${
                            selected === p.user_id
                                ? "border-[hsl(355,93%,46%)] bg-[hsl(355,93%,46%)]/15"
                                : "border-white/10 bg-card hover:border-white/30"
                        }`}
                    >
                        <div className="font-display font-bold text-lg">{p.display_name}</div>
                        <div className="text-xs text-white/50 font-body">@{p.username}</div>
                    </button>
                ))}
            </div>
            <Button
                data-testid="confirm-night-btn"
                disabled={!selected || busy}
                onClick={() => onSubmit(selected)}
                className="w-full h-14 text-lg font-display font-extrabold bg-[hsl(355,93%,46%)] hover:bg-[hsl(355,93%,40%)] transition-colors"
            >
                تأكيد
            </Button>
        </div>
    );
}
