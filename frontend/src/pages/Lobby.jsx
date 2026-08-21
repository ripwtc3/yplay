import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import { Copy, Play, LogOut, Users, Crown, Wifi, WifiOff } from "lucide-react";

export default function Lobby() {
    const { roomId } = useParams();
    const nav = useNavigate();
    const { user, addListener, subscribeRoom, wsReady } = useAuth();
    const [room, setRoom] = useState(null);
    const [players, setPlayers] = useState([]);
    const [starting, setStarting] = useState(false);

    const load = async () => {
        try {
            const r = await api.get(`/rooms/${roomId}`);
            setRoom(r.data);
            setPlayers(r.data.players || []);
            if (r.data.status === "ACTIVE") {
                nav(`/game/${roomId}`, { replace: true });
            }
        } catch (err) {
            toast.error(err.response?.data?.detail || "تعذر تحميل الغرفة");
            nav("/dashboard");
        }
    };

    useEffect(() => { load(); }, [roomId]);

    useEffect(() => {
        if (wsReady) subscribeRoom(roomId);
    }, [wsReady, roomId]);

    useEffect(() => {
        const off = addListener((msg) => {
            if (msg.type === "PLAYER_JOINED" || msg.type === "PLAYER_LEFT" || msg.type === "PLAYER_ONLINE" || msg.type === "PLAYER_OFFLINE") {
                if (msg.players) setPlayers(msg.players);
                if (msg.type === "PLAYER_JOINED" && msg.user?.user_id !== user?.id) toast.info(`انضم ${msg.user.display_name}`);
            } else if (msg.type === "GAME_STARTED") {
                nav(`/game/${roomId}`);
            } else if (msg.type === "ROOM_CANCELLED") {
                toast.warning("تم إلغاء الغرفة");
                nav("/dashboard");
            }
        });
        return off;
    }, [addListener, roomId, user, nav]);

    const copy = () => {
        if (!room) return;
        navigator.clipboard.writeText(room.room_code);
        toast.success("تم نسخ الكود");
    };

    const start = async () => {
        setStarting(true);
        try {
            await api.post(`/rooms/${roomId}/start`);
        } catch (err) {
            toast.error(err.response?.data?.detail || "لا يمكن البدء الآن");
        } finally { setStarting(false); }
    };

    const leave = async () => {
        try {
            await api.post(`/rooms/${roomId}/leave`);
            nav("/dashboard");
        } catch (err) {
            toast.error(err.response?.data?.detail || "خطأ");
        }
    };

    if (!room) return <div className="min-h-screen grid place-items-center text-white/60 font-body">جاري التحميل...</div>;

    const isHost = user?.id === room.host_id;
    const canStart = isHost && players.length >= room.max_players;

    return (
        <div className="min-h-screen">
            <nav className="sticky top-0 z-40 backdrop-blur-xl bg-black/60 border-b border-white/10">
                <div className="max-w-5xl mx-auto flex items-center justify-between px-6 py-4">
                    <div className="font-display text-lg font-extrabold">{room.name}</div>
                    <Button data-testid="leave-room-btn" onClick={leave} variant="ghost" className="text-red-400 hover:bg-red-500/10">
                        <LogOut className="w-4 h-4 ms-2" /> {isHost ? "إلغاء الغرفة" : "مغادرة"}
                    </Button>
                </div>
            </nav>

            <div className="max-w-5xl mx-auto px-6 py-12">
                {/* Room Code */}
                <div className="rounded-2xl border border-[hsl(355,93%,46%)]/30 bg-gradient-to-br from-[hsl(355,93%,46%)]/10 to-transparent p-8 text-center fade-in-up">
                    <div className="text-white/60 text-sm font-body mb-2">كود الغرفة</div>
                    <div className="flex items-center justify-center gap-4">
                        <div data-testid="room-code-display" className="font-display text-5xl sm:text-7xl font-black tracking-[0.3em] text-shadow-red">{room.room_code}</div>
                        <button data-testid="copy-code-btn" onClick={copy} className="p-3 rounded-xl border border-white/10 bg-black/40 hover:bg-white/5 transition-colors">
                            <Copy className="w-6 h-6" />
                        </button>
                    </div>
                    <p className="mt-4 text-white/60 font-body">شارك الكود مع أصحابك · اللاعبون: <span className="font-display font-bold text-white" data-testid="player-count">{players.length}/{room.max_players}</span></p>
                </div>

                {/* Players list */}
                <div className="mt-8">
                    <div className="flex items-center gap-2 mb-4">
                        <Users className="w-5 h-5 text-white/60" />
                        <h3 className="font-display text-xl font-bold">اللاعبون</h3>
                    </div>
                    <div className="grid sm:grid-cols-2 md:grid-cols-3 gap-3">
                        {players.map((p, i) => (
                            <div
                                key={p.user_id}
                                data-testid={`lobby-player-${p.user_id}`}
                                className="rounded-xl border border-white/10 bg-card p-4 flex items-center gap-3 fade-in-up"
                                style={{ animationDelay: `${i * 40}ms` }}
                            >
                                <div className="w-10 h-10 rounded-full bg-gradient-to-br from-[hsl(355,93%,46%)]/40 to-[hsl(240,10%,20%)] grid place-items-center font-display font-bold">
                                    {p.display_name?.[0] || "?"}
                                </div>
                                <div className="flex-1 min-w-0">
                                    <div className="font-body font-bold flex items-center gap-1 truncate">
                                        {p.display_name}
                                        {p.is_host && <Crown className="w-3.5 h-3.5 text-yellow-400" />}
                                    </div>
                                    <div className="text-xs text-white/50 font-body truncate">@{p.username}</div>
                                </div>
                                {p.connection_status === "ONLINE" ? <Wifi className="w-4 h-4 text-emerald-400" /> : <WifiOff className="w-4 h-4 text-white/30" />}
                            </div>
                        ))}
                        {Array.from({ length: Math.max(0, room.max_players - players.length) }).map((_, i) => (
                            <div key={`slot-${i}`} className="rounded-xl border border-dashed border-white/10 bg-black/20 p-4 text-white/30 text-sm font-body grid place-items-center">
                                مقعد شاغر...
                            </div>
                        ))}
                    </div>
                </div>

                {/* Host controls */}
                {isHost && (
                    <div className="mt-10 sticky bottom-4">
                        <Button
                            data-testid="start-game-btn"
                            disabled={!canStart || starting}
                            onClick={start}
                            className="w-full h-16 text-xl font-display font-extrabold bg-[hsl(355,93%,46%)] hover:bg-[hsl(355,93%,40%)] disabled:bg-white/10 transition-colors"
                        >
                            <Play className="w-6 h-6 ms-2" />
                            {canStart ? "بدء اللعبة" : `بانتظار ${room.max_players - players.length} لاعبين`}
                        </Button>
                    </div>
                )}
            </div>
        </div>
    );
}
