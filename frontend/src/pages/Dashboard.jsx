import { useNavigate } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import { Button } from "@/components/ui/button";
import { Gamepad2, Users, LogOut, Skull, Trophy, Play, UserCircle, Stethoscope, Search, User as UserIcon } from "lucide-react";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";

const ROLE_ICONS = { MAFIA: Skull, CITIZEN: UserIcon, DOCTOR: Stethoscope, DETECTIVE: Search };
const ROLE_COLORS = { MAFIA: "text-[hsl(355,93%,60%)]", CITIZEN: "text-white/80", DOCTOR: "text-emerald-400", DETECTIVE: "text-cyan-400" };
const ROLE_AR = { MAFIA: "Mafia", CITIZEN: "Citizen", DOCTOR: "Doctor", DETECTIVE: "Detective" };

export default function Dashboard() {
    const { user, logout } = useAuth();
    const nav = useNavigate();
    const [activeRoom, setActiveRoom] = useState(null);
    const [stats, setStats] = useState(null);

    useEffect(() => {
        api.get("/rooms/mine").then((r) => setActiveRoom(r.data.room)).catch(() => {});
        api.get("/users/me/stats").then((r) => setStats(r.data)).catch(() => {});
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
                    <div className="flex items-center gap-2">
                        <Button data-testid="nav-profile-btn" onClick={() => nav("/profile")} variant="ghost" className="text-white/70 hover:bg-white/10">
                            <UserCircle className="w-4 h-4 ms-2" /> حسابي
                        </Button>
                        <Button data-testid="logout-btn" onClick={() => { logout(); nav("/"); }} variant="ghost" className="text-white/70 hover:bg-white/10">
                            <LogOut className="w-4 h-4 ms-2" /> خروج
                        </Button>
                    </div>
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

                <div className="mt-12 rounded-2xl border border-white/10 bg-card p-6" data-testid="stats-section">
                    <div className="flex items-center gap-3 mb-4">
                        <Trophy className="w-5 h-5 text-yellow-400" />
                        <h4 className="font-display font-bold text-lg">إحصائياتك</h4>
                    </div>
                    {!stats || stats.total_games === 0 ? (
                        <p className="text-white/50 text-sm font-body">لم تلعب أي مباراة بعد — أنشئ غرفة أو انضم بكود لبدء الرحلة.</p>
                    ) : (
                        <>
                            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-6">
                                <div className="rounded-xl border border-white/10 bg-black/30 p-4">
                                    <div className="text-xs text-white/50 font-body">مباريات</div>
                                    <div className="font-display text-3xl font-black mt-1" data-testid="stat-total">{stats.total_games}</div>
                                </div>
                                <div className="rounded-xl border border-emerald-500/30 bg-emerald-500/10 p-4">
                                    <div className="text-xs text-emerald-300 font-body">فوز</div>
                                    <div className="font-display text-3xl font-black mt-1 text-emerald-300" data-testid="stat-wins">{stats.wins}</div>
                                </div>
                                <div className="rounded-xl border border-[hsl(355,93%,46%)]/30 bg-[hsl(355,93%,46%)]/10 p-4">
                                    <div className="text-xs text-[hsl(355,93%,70%)] font-body">خسارة</div>
                                    <div className="font-display text-3xl font-black mt-1 text-[hsl(355,93%,70%)]" data-testid="stat-losses">{stats.losses}</div>
                                </div>
                                <div className="rounded-xl border border-yellow-500/30 bg-yellow-500/10 p-4">
                                    <div className="text-xs text-yellow-300 font-body">نسبة الفوز</div>
                                    <div className="font-display text-3xl font-black mt-1 text-yellow-300" data-testid="stat-winrate">{Math.round(stats.win_rate * 100)}%</div>
                                </div>
                            </div>

                            {/* Roles breakdown */}
                            <div className="mb-4">
                                <div className="text-xs text-white/50 font-body mb-2">أدائك حسب الدور</div>
                                <div className="grid sm:grid-cols-2 md:grid-cols-4 gap-2">
                                    {Object.entries(stats.role_stats).map(([role, s]) => {
                                        const Icon = ROLE_ICONS[role];
                                        const wr = s.played ? Math.round((s.won / s.played) * 100) : 0;
                                        return (
                                            <div key={role} data-testid={`role-stat-${role}`} className={`rounded-lg border border-white/10 bg-black/30 p-3 ${stats.best_role === role ? "ring-2 ring-yellow-400/40" : ""}`}>
                                                <div className="flex items-center gap-2">
                                                    <Icon className={`w-4 h-4 ${ROLE_COLORS[role]}`} />
                                                    <span className="font-display font-bold text-sm">{ROLE_AR[role]}</span>
                                                    {stats.best_role === role && <span className="text-[10px] text-yellow-300">⭐</span>}
                                                </div>
                                                <div className="mt-1 text-xs text-white/60 font-body">
                                                    {s.played} مباراة · {wr}% فوز
                                                </div>
                                            </div>
                                        );
                                    })}
                                </div>
                            </div>

                            {/* Recent games */}
                            {stats.recent.length > 0 && (
                                <div>
                                    <div className="text-xs text-white/50 font-body mb-2">آخر المباريات</div>
                                    <div className="space-y-2">
                                        {stats.recent.map((g, i) => {
                                            const Icon = ROLE_ICONS[g.role];
                                            return (
                                                <div key={i} data-testid={`recent-game-${i}`} className="rounded-lg border border-white/10 bg-black/30 p-3 flex items-center justify-between gap-3">
                                                    <div className="flex items-center gap-2">
                                                        <Icon className={`w-4 h-4 ${ROLE_COLORS[g.role]}`} />
                                                        <span className="font-body text-sm">{ROLE_AR[g.role]}</span>
                                                        <span className="text-xs text-white/40">·</span>
                                                        <span className="text-xs text-white/50 font-body">{g.rounds} جولة</span>
                                                    </div>
                                                    <div className="flex items-center gap-2">
                                                        {g.survived && <span className="text-[10px] px-2 py-0.5 rounded-full bg-cyan-500/20 text-cyan-300 font-body">نجا</span>}
                                                        <span className={`text-xs px-2 py-0.5 rounded-full font-display font-bold ${g.won ? "bg-emerald-500/20 text-emerald-300" : "bg-[hsl(355,93%,46%)]/20 text-[hsl(355,93%,70%)]"}`}>
                                                            {g.won ? "فوز" : "خسارة"}
                                                        </span>
                                                    </div>
                                                </div>
                                            );
                                        })}
                                    </div>
                                </div>
                            )}
                        </>
                    )}
                </div>
            </div>
        </div>
    );
}
