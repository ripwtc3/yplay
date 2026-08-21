import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { toast } from "sonner";
import { ArrowRight, KeyRound } from "lucide-react";

export default function JoinRoom() {
    const [code, setCode] = useState("");
    const [busy, setBusy] = useState(false);
    const nav = useNavigate();

    const join = async (e) => {
        e.preventDefault();
        if (!code.trim()) return;
        setBusy(true);
        try {
            const res = await api.post("/rooms/join", { room_code: code.trim().toUpperCase() });
            toast.success("تم الانضمام");
            nav(`/room/${res.data.id}`);
        } catch (err) {
            toast.error(err.response?.data?.detail || "تعذر الانضمام");
        } finally { setBusy(false); }
    };

    return (
        <div className="min-h-screen grid place-items-center px-6 py-12 noise-bg">
            <div className="w-full max-w-md">
                <button data-testid="back-btn" onClick={() => nav(-1)} className="text-white/60 hover:text-white mb-6 font-body flex items-center gap-2">
                    <ArrowRight className="w-4 h-4" /> رجوع
                </button>
                <div className="rounded-2xl border border-white/10 bg-card p-8 fade-in-up">
                    <div className="w-14 h-14 rounded-xl bg-cyan-500/20 grid place-items-center mb-4">
                        <KeyRound className="w-7 h-7 text-cyan-400" />
                    </div>
                    <h1 className="font-display text-3xl font-extrabold">دخول غرفة</h1>
                    <p className="text-white/60 mt-2 mb-6 font-body">أدخل كود الغرفة الذي شاركه صاحبك</p>
                    <form onSubmit={join} className="space-y-5">
                        <Input
                            data-testid="room-code-input"
                            value={code}
                            onChange={(e) => setCode(e.target.value.toUpperCase())}
                            placeholder="A7K9M2"
                            maxLength={10}
                            className="h-16 text-center text-3xl tracking-[0.4em] font-display font-black bg-black/40 border-white/10 focus:ring-cyan-400"
                            autoFocus
                        />
                        <Button
                            data-testid="join-room-btn"
                            type="submit"
                            disabled={busy || code.length < 4}
                            className="w-full h-14 text-lg font-display font-extrabold bg-cyan-500 hover:bg-cyan-600 transition-colors"
                        >
                            {busy ? "جاري..." : "دخول"}
                        </Button>
                    </form>
                </div>
            </div>
        </div>
    );
}
