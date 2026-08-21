import { Link, useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/context/AuthContext";
import { Skull, Users, Gamepad2, Sparkles, Brain, Grid3x3, Dice5, Timer, LogIn } from "lucide-react";

const HERO_IMG = "https://images.unsplash.com/photo-1761845081361-57b8453ce682?crop=entropy&cs=srgb&fm=jpg&ixid=M3w3NDQ2MzR8MHwxfHNlYXJjaHw0fHxtYWZpYSUyMG5pZ2h0JTIwY2l0eSUyMGRhcmslMjBteXN0ZXJpb3VzfGVufDB8fHx8MTc4NzI3MzA4NXww&ixlib=rb-4.1.0&q=85";

const games = [
    { name: "Mafia", desc: "لعبة الأدوار السرية الأشهر", icon: Skull, active: true, color: "text-[hsl(355,93%,60%)]" },
    { name: "Quiz", desc: "منافسات الأسئلة السريعة", icon: Brain, active: false, color: "text-cyan-400" },
    { name: "Bingo", desc: "كلاسيك عائلي بنكهة عربية", icon: Grid3x3, active: false, color: "text-yellow-400" },
    { name: "Roulette", desc: "دولاب الحظ الجماعي", icon: Dice5, active: false, color: "text-fuchsia-400" },
    { name: "Word Rush", desc: "سباق الكلمات", icon: Timer, active: false, color: "text-orange-400" },
    { name: "Memory Match", desc: "الذاكرة والتركيز", icon: Sparkles, active: false, color: "text-emerald-400" },
];

export default function Landing() {
    const nav = useNavigate();
    const { user } = useAuth();

    return (
        <div className="min-h-screen">
            {/* NAV */}
            <nav className="sticky top-0 z-40 backdrop-blur-xl bg-black/60 border-b border-white/10">
                <div className="max-w-7xl mx-auto flex items-center justify-between px-6 py-4">
                    <div className="flex items-center gap-3 font-display">
                        <div className="w-9 h-9 rounded-lg bg-gradient-to-br from-[hsl(355,93%,46%)] to-[hsl(355,93%,26%)] grid place-items-center">
                            <Skull className="w-5 h-5 text-white" />
                        </div>
                        <span className="text-xl font-extrabold tracking-tight">لايف <span className="text-[hsl(355,93%,60%)]">ألعاب</span></span>
                    </div>
                    <div className="flex items-center gap-3">
                        {user ? (
                            <Button data-testid="nav-dashboard-btn" onClick={() => nav("/dashboard")} className="bg-[hsl(355,93%,46%)] hover:bg-[hsl(355,93%,40%)]">
                                لوحتي
                            </Button>
                        ) : (
                            <>
                                <Link to="/login"><Button data-testid="nav-login-btn" variant="ghost" className="text-white hover:bg-white/10"><LogIn className="w-4 h-4 ms-2" /> دخول</Button></Link>
                                <Link to="/register"><Button data-testid="nav-register-btn" className="bg-[hsl(355,93%,46%)] hover:bg-[hsl(355,93%,40%)]">إنشاء حساب</Button></Link>
                            </>
                        )}
                    </div>
                </div>
            </nav>

            {/* HERO */}
            <section className="relative overflow-hidden noise-bg">
                <div className="absolute inset-0 -z-10">
                    <img src={HERO_IMG} alt="" className="w-full h-full object-cover opacity-30" />
                    <div className="absolute inset-0 bg-gradient-to-b from-transparent via-black/70 to-background" />
                </div>
                <div className="max-w-7xl mx-auto px-6 py-24 lg:py-36 grid lg:grid-cols-2 gap-12 items-center">
                    <div className="fade-in-up">
                        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full border border-[hsl(355,93%,46%)]/40 bg-[hsl(355,93%,46%)]/10 text-[hsl(355,93%,70%)] text-sm mb-6 font-body">
                            <span className="w-2 h-2 rounded-full bg-[hsl(355,93%,46%)] pulse-glow"></span>
                            متعدد اللاعبين · مباشر · بدون تحميل
                        </div>
                        <h1 className="font-display text-4xl sm:text-5xl lg:text-6xl font-extrabold leading-tight text-shadow-red">
                            ألعاب جماعية <span className="text-[hsl(355,93%,60%)]">تفاعلية</span>
                            <br />العب مع أصحابك أو جمهورك مباشرة
                        </h1>
                        <p className="mt-6 text-lg text-white/70 leading-relaxed max-w-xl font-body">
                            منصة عربية بالكامل للعب Mafia وألعاب جماعية أخرى Real-Time.
                            أنشئ غرفة، شارك الكود، وابدأ اللعب في ثواني.
                        </p>
                        <div className="mt-10 flex flex-col sm:flex-row gap-4">
                            <Button
                                data-testid="hero-create-btn"
                                onClick={() => nav(user ? "/create" : "/register")}
                                className="h-14 px-8 text-lg font-display font-bold bg-[hsl(355,93%,46%)] hover:bg-[hsl(355,93%,40%)] hover:scale-[1.03] transition-transform"
                            >
                                <Gamepad2 className="w-5 h-5 ms-2" /> إنشاء لعبة
                            </Button>
                            <Button
                                data-testid="hero-join-btn"
                                onClick={() => nav(user ? "/join" : "/login")}
                                variant="outline"
                                className="h-14 px-8 text-lg font-display font-bold border-white/20 bg-white/5 hover:bg-white/10 hover:scale-[1.03] transition-transform"
                            >
                                <Users className="w-5 h-5 ms-2" /> دخول غرفة
                            </Button>
                        </div>
                    </div>
                    <div className="hidden lg:block relative">
                        <div className="absolute -inset-8 bg-[hsl(355,93%,46%)]/20 blur-3xl rounded-full"></div>
                        <div className="relative rounded-2xl border border-white/10 overflow-hidden bg-black/40 backdrop-blur">
                            <img src={HERO_IMG} alt="mafia" className="w-full h-96 object-cover opacity-80" />
                        </div>
                    </div>
                </div>
            </section>

            {/* GAMES GRID */}
            <section className="max-w-7xl mx-auto px-6 py-20">
                <div className="mb-12">
                    <h2 className="font-display text-3xl sm:text-4xl font-extrabold">الألعاب المتاحة</h2>
                    <p className="text-white/60 mt-2 font-body">Mafia متاحة الآن · المزيد قادم قريباً</p>
                </div>
                <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-6">
                    {games.map((g, i) => (
                        <div
                            key={g.name}
                            data-testid={`game-card-${g.name.toLowerCase().replace(" ", "-")}`}
                            className={`group relative rounded-2xl border p-8 overflow-hidden fade-in-up ${
                                g.active
                                    ? "border-[hsl(355,93%,46%)]/40 bg-gradient-to-br from-[hsl(355,93%,46%)]/10 to-transparent hover:from-[hsl(355,93%,46%)]/20 cursor-pointer"
                                    : "border-white/10 bg-white/[0.02] opacity-70"
                            } transition-colors`}
                            style={{ animationDelay: `${i * 60}ms` }}
                            onClick={() => g.active && nav(user ? "/create" : "/register")}
                        >
                            <div className="flex items-start justify-between mb-6">
                                <g.icon className={`w-10 h-10 ${g.color}`} />
                                {g.active ? (
                                    <span className="text-xs px-2 py-1 rounded-full bg-[hsl(355,93%,46%)] text-white font-display font-bold">متاحة</span>
                                ) : (
                                    <span className="text-xs px-2 py-1 rounded-full bg-white/10 text-white/60 font-body">قريباً</span>
                                )}
                            </div>
                            <h3 className="font-display text-2xl font-bold">{g.name}</h3>
                            <p className="text-white/60 mt-2 font-body">{g.desc}</p>
                        </div>
                    ))}
                </div>
            </section>

            <footer className="border-t border-white/10 py-8 text-center text-white/40 text-sm font-body">
                © 2026 لايف ألعاب · صُنعت بحب للمجتمع العربي
            </footer>
        </div>
    );
}
