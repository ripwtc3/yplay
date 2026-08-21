import { useNavigate } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import { Button } from "@/components/ui/button";
import { Gamepad2, Users, LogOut, Skull, Trophy, Play } from "lucide-react";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";

export default function Dashboard() {
    const { user, logout } = useAuth();
    const nav = useNavigate();
    const [activeRoom, setActiveRoom] = useState(null);

    useEffect(() => {
        api.get("/rooms/mine").then((r) => setActiveRoom(r.data.room)).catch(() => {});
    }, []);

    return (
        <div className="min-h-screen">
            <nav className="sticky top-0 z-40 backdrop-blur-xl bg-black/60 border-b border-white/10">
                <div className="max-w-7xl mx-auto flex items-center justify-between px-6 py-4">
                    <div className="flex items-center gap-3 font-display">
                        <div className="w-9 h-9 rounded-lg bg-gradient-to-br from-[hsl(355,93%,46%)] to-[hsl(355,93%,26%)] grid place-items-center">
                            <Skull className="w-5 h-5 text-white" />
                        </div>
                        <span className="text-xl font-extrabold">لايف <span className="text-[hsl(355,93%,60%)]">ألعاب</span></span>
                    </div>
                    <Button data-testid="logout-btn" onClick={() => { logout(); nav("/"); }} variant="ghost" className="text-white/70 hover:bg-white/10">
                        <LogOut className="w-4 h-4 ms-2" /> خروج
                    </Button>
                </div>
            </nav>

            <div className="max-w-7xl mx-auto px-6 py-12">
                <div className="fade-in-up">
                    <h1 className="font-display text-4xl sm:text-5xl font-extrabold">أهلاً <span className="text-[hsl(355,93%,60%)]">{user?.display_name}</span> 👋</h1>
                    <p className="text-white/60 mt-3 font-body">اختر إنشاء غرفة جديدة أو انضم بكود لغرفة أصحابك</p>
                </div>

                {activeRoom && (
                    <div data-testid="active-room-card" className="mt-10 rounded-2xl border border-[hsl(355,93%,46%)]/40 bg-gradient-to-br from-[hsl(355,93%,46%)]/10 to-transparent p-6 fade-in-up">
                        <div className="flex flex-wrap items-center justify-between gap-4">
                            <div>
                                <div className="text-white/60 text-sm font-body">غرفة نشطة</div>
                                <div className="font-display text-2xl font-bold mt-1">{activeRoom.name}</div>
                                <div className="text-white/60 mt-1 font-body">
                                    كود: <span className="font-display tracking-widest text-white">{activeRoom.room_code}</span> · لاعبون: {activeRoom.player_count}/{activeRoom.max_players}
                                </div>
                            </div>
                            <Button
                                data-testid="rejoin-room-btn"
                                onClick={() => nav(activeRoom.status === "ACTIVE" ? `/game/${activeRoom.id}` : `/room/${activeRoom.id}`)}
                                className="h-12 px-6 bg-[hsl(355,93%,46%)] hover:bg-[hsl(355,93%,40%)] font-display font-bold"
                            >
                                <Play className="w-5 h-5 ms-2" /> العودة للغرفة
                            </Button>
                        </div>
                    </div>
                )}

                <div className="mt-10 grid md:grid-cols-2 gap-6">
                    <button
                        data-testid="dashboard-create-btn"
                        onClick={() => nav("/create")}
                        className="text-right rounded-2xl border border-white/10 bg-gradient-to-br from-[hsl(355,93%,46%)]/20 to-transparent p-8 hover:border-[hsl(355,93%,46%)]/60 transition-colors group"
                    >
                        <Gamepad2 className="w-12 h-12 text-[hsl(355,93%,60%)] mb-4" />
                        <h3 className="font-display text-2xl font-extrabold">إنشاء لعبة</h3>
                        <p className="text-white/60 mt-2 font-body">أنشئ غرفة Mafia واحصل على كود لمشاركته</p>
                    </button>
                    <button
                        data-testid="dashboard-join-btn"
                        onClick={() => nav("/join")}
                        className="text-right rounded-2xl border border-white/10 bg-gradient-to-br from-cyan-500/10 to-transparent p-8 hover:border-cyan-500/50 transition-colors"
                    >
                        <Users className="w-12 h-12 text-cyan-400 mb-4" />
                        <h3 className="font-display text-2xl font-extrabold">دخول غرفة</h3>
                        <p className="text-white/60 mt-2 font-body">أدخل كود الغرفة الذي شاركه صديقك</p>
                    </button>
                </div>

                <div className="mt-12 rounded-2xl border border-white/10 bg-card p-6">
                    <div className="flex items-center gap-3 mb-2">
                        <Trophy className="w-5 h-5 text-yellow-400" />
                        <h4 className="font-display font-bold">إحصائياتك</h4>
                    </div>
                    <p className="text-white/50 text-sm font-body">قريباً — سنعرض عدد ألعابك، انتصاراتك، وأدوارك المفضلة.</p>
                </div>
            </div>
        </div>
    );
}
