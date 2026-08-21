import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { toast } from "sonner";
import { ArrowRight, Skull, Stethoscope, Search, Moon, MessageSquare, Sun, Vote as VoteIcon } from "lucide-react";

export default function CreateGame() {
    const nav = useNavigate();
    const [busy, setBusy] = useState(false);
    const [name, setName] = useState("ليلة سرية");
    const [s, setS] = useState({
        max_players: 6,
        mafia_count: 1,
        doctor_count: 1,
        detective_count: 1,
        mafia_discussion_seconds: 20,
        night_actions_seconds: 30,
        discussion_seconds: 60,
        voting_seconds: 30,
        reveal_eliminated_role: false,
        host_can_view_mafia_chat: false,
    });

    const num = (k, min, max) => (
        <div className="flex items-center gap-3 justify-between">
            <span className="font-body text-white/80 text-sm">{k.label}</span>
            <div className="flex items-center gap-2">
                <button
                    data-testid={`${k.field}-dec-btn`}
                    className="w-9 h-9 rounded-lg border border-white/10 bg-black/40 hover:bg-white/5 transition-colors font-display font-bold"
                    onClick={() => setS({ ...s, [k.field]: Math.max(min, s[k.field] - 1) })}
                    type="button"
                >−</button>
                <div data-testid={`${k.field}-value`} className="w-14 text-center font-display font-extrabold text-2xl">{s[k.field]}</div>
                <button
                    data-testid={`${k.field}-inc-btn`}
                    className="w-9 h-9 rounded-lg border border-white/10 bg-black/40 hover:bg-white/5 transition-colors font-display font-bold"
                    onClick={() => setS({ ...s, [k.field]: Math.min(max, s[k.field] + 1) })}
                    type="button"
                >+</button>
            </div>
        </div>
    );

    const create = async () => {
        setBusy(true);
        try {
            const res = await api.post("/rooms", { name, game_type: "mafia", settings: s });
            toast.success("تم إنشاء الغرفة");
            nav(`/room/${res.data.id}`);
        } catch (err) {
            toast.error(err.response?.data?.detail || "فشل إنشاء الغرفة");
        } finally { setBusy(false); }
    };

    const totalSpecial = s.mafia_count + s.doctor_count + s.detective_count;
    const citizens = Math.max(0, s.max_players - totalSpecial);

    return (
        <div className="min-h-screen">
            <div className="max-w-3xl mx-auto px-6 py-12">
                <button data-testid="back-btn" onClick={() => nav(-1)} className="text-white/60 hover:text-white mb-6 font-body flex items-center gap-2">
                    <ArrowRight className="w-4 h-4" /> رجوع
                </button>
                <h1 className="font-display text-4xl font-extrabold mb-2">إعدادات لعبة <span className="text-[hsl(355,93%,60%)]">Mafia</span></h1>
                <p className="text-white/60 font-body mb-8">اضبط إعدادات الغرفة قبل إرسال الكود لأصحابك</p>

                <div className="rounded-2xl border border-white/10 bg-card p-6 space-y-6 fade-in-up">
                    <div>
                        <Label className="font-body">اسم الغرفة</Label>
                        <Input data-testid="room-name-input" value={name} onChange={(e) => setName(e.target.value)} className="mt-2 h-12 bg-black/40 border-white/10" />
                    </div>

                    <div className="grid sm:grid-cols-2 gap-4">
                        <div className="rounded-xl border border-white/10 p-4 bg-black/30">
                            {num({ field: "max_players", label: "عدد اللاعبين" }, 4, 20)}
                        </div>
                        <div className="rounded-xl border border-white/10 p-4 bg-black/30">
                            <div className="flex items-center gap-2 mb-3"><Skull className="w-4 h-4 text-[hsl(355,93%,60%)]" /> <span className="font-body font-bold">Mafia</span></div>
                            {num({ field: "mafia_count", label: "عدد الـMafia" }, 1, 6)}
                        </div>
                        <div className="rounded-xl border border-white/10 p-4 bg-black/30">
                            <div className="flex items-center gap-2 mb-3"><Stethoscope className="w-4 h-4 text-emerald-400" /> <span className="font-body font-bold">Doctor</span></div>
                            {num({ field: "doctor_count", label: "عدد Doctors" }, 0, 3)}
                        </div>
                        <div className="rounded-xl border border-white/10 p-4 bg-black/30">
                            <div className="flex items-center gap-2 mb-3"><Search className="w-4 h-4 text-cyan-400" /> <span className="font-body font-bold">Detective</span></div>
                            {num({ field: "detective_count", label: "عدد Detectives" }, 0, 3)}
                        </div>
                    </div>

                    <div className="rounded-xl border border-[hsl(355,93%,46%)]/30 bg-[hsl(355,93%,46%)]/10 p-4 font-body">
                        <div className="text-white/80">توزيع الأدوار: <b>{s.mafia_count}</b> Mafia · <b>{s.doctor_count}</b> Doctor · <b>{s.detective_count}</b> Detective · <b>{citizens}</b> Citizens</div>
                        {totalSpecial >= s.max_players && <div className="text-red-300 text-sm mt-1">مجموع الأدوار الخاصة يجب أن يكون أقل من عدد اللاعبين</div>}
                    </div>

                    {/* Night settings section */}
                    <div className="rounded-xl border border-white/10 p-4 bg-gradient-to-br from-cyan-500/5 to-transparent">
                        <div className="flex items-center gap-2 mb-4"><Moon className="w-4 h-4 text-cyan-300" /> <span className="font-display font-bold">إعدادات الليل</span></div>
                        <div className="grid sm:grid-cols-2 gap-3">
                            <div className="rounded-lg border border-white/10 p-3 bg-black/30">
                                <div className="text-xs text-white/50 mb-2 font-body flex items-center gap-1"><MessageSquare className="w-3 h-3" /> اجتماع Mafia</div>
                                {num({ field: "mafia_discussion_seconds", label: "المدة (ث)" }, 10, 180)}
                            </div>
                            <div className="rounded-lg border border-white/10 p-3 bg-black/30">
                                <div className="text-xs text-white/50 mb-2 font-body flex items-center gap-1"><Skull className="w-3 h-3" /> حركات الليل</div>
                                {num({ field: "night_actions_seconds", label: "المدة (ث)" }, 15, 180)}
                            </div>
                        </div>
                    </div>

                    <div className="rounded-xl border border-white/10 p-4 bg-gradient-to-br from-yellow-500/5 to-transparent">
                        <div className="flex items-center gap-2 mb-4"><Sun className="w-4 h-4 text-yellow-300" /> <span className="font-display font-bold">إعدادات النهار</span></div>
                        <div className="grid sm:grid-cols-2 gap-3">
                            <div className="rounded-lg border border-white/10 p-3 bg-black/30">
                                <div className="text-xs text-white/50 mb-2 font-body">النقاش (ث)</div>
                                {num({ field: "discussion_seconds", label: "المدة" }, 15, 300)}
                            </div>
                            <div className="rounded-lg border border-white/10 p-3 bg-black/30">
                                <div className="text-xs text-white/50 mb-2 font-body flex items-center gap-1"><VoteIcon className="w-3 h-3" /> التصويت (ث)</div>
                                {num({ field: "voting_seconds", label: "المدة" }, 15, 180)}
                            </div>
                        </div>
                    </div>

                    <div className="flex items-center justify-between rounded-xl border border-white/10 p-4 bg-black/30">
                        <div>
                            <div className="font-body font-bold">إظهار دور اللاعب بعد خروجه</div>
                            <div className="text-white/50 text-sm font-body mt-1">Reveal Eliminated Role</div>
                        </div>
                        <Switch data-testid="reveal-role-switch" checked={s.reveal_eliminated_role} onCheckedChange={(v) => setS({ ...s, reveal_eliminated_role: v })} />
                    </div>

                    <div className="flex items-center justify-between rounded-xl border border-white/10 p-4 bg-black/30">
                        <div>
                            <div className="font-body font-bold">مشاهدة Chat Mafia للـHost</div>
                            <div className="text-white/50 text-sm font-body mt-1">مفيد للبث — لا يستطيع الكتابة بل يشاهد فقط</div>
                        </div>
                        <Switch data-testid="host-view-mafia-switch" checked={s.host_can_view_mafia_chat} onCheckedChange={(v) => setS({ ...s, host_can_view_mafia_chat: v })} />
                    </div>

                    <Button
                        data-testid="create-room-btn"
                        onClick={create}
                        disabled={busy || totalSpecial >= s.max_players}
                        className="w-full h-14 text-lg font-display font-extrabold bg-[hsl(355,93%,46%)] hover:bg-[hsl(355,93%,40%)] transition-colors"
                    >
                        {busy ? "جاري الإنشاء..." : "إنشاء الغرفة"}
                    </Button>
                </div>
            </div>
        </div>
    );
}
