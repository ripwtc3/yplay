import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { toast } from "sonner";
import { Skull } from "lucide-react";

export default function Login() {
    const [email, setEmail] = useState("");
    const [password, setPassword] = useState("");
    const [busy, setBusy] = useState(false);
    const { login } = useAuth();
    const nav = useNavigate();

    const submit = async (e) => {
        e.preventDefault();
        setBusy(true);
        try {
            await login(email, password);
            toast.success("تم الدخول");
            nav("/dashboard");
        } catch (err) {
            toast.error(err.response?.data?.detail || "فشل تسجيل الدخول");
        } finally { setBusy(false); }
    };

    return (
        <div className="min-h-screen grid place-items-center px-6 py-16 noise-bg">
            <div className="w-full max-w-md">
                <div className="flex items-center gap-3 mb-8 font-display">
                    <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-[hsl(355,93%,46%)] to-[hsl(355,93%,26%)] grid place-items-center">
                        <Skull className="w-5 h-5 text-white" />
                    </div>
                    <span className="text-2xl font-extrabold">لايف <span className="text-[hsl(355,93%,60%)]">ألعاب</span></span>
                </div>
                <div className="rounded-2xl border border-white/10 bg-card p-8 fade-in-up">
                    <h1 className="font-display text-3xl font-extrabold mb-2">أهلاً بعودتك</h1>
                    <p className="text-white/60 mb-8 font-body">سجل الدخول للعودة إلى غرفتك أو إنشاء لعبة جديدة</p>
                    <form onSubmit={submit} className="space-y-5">
                        <div>
                            <Label className="font-body">البريد الإلكتروني</Label>
                            <Input data-testid="login-email-input" type="email" value={email} onChange={(e) => setEmail(e.target.value)} required className="mt-2 h-12 bg-black/40 border-white/10 focus:ring-[hsl(355,93%,46%)]" />
                        </div>
                        <div>
                            <Label className="font-body">كلمة المرور</Label>
                            <Input data-testid="login-password-input" type="password" value={password} onChange={(e) => setPassword(e.target.value)} required className="mt-2 h-12 bg-black/40 border-white/10 focus:ring-[hsl(355,93%,46%)]" />
                        </div>
                        <Button data-testid="login-submit-btn" type="submit" disabled={busy} className="w-full h-12 font-display font-bold text-base bg-[hsl(355,93%,46%)] hover:bg-[hsl(355,93%,40%)] transition-colors">
                            {busy ? "جاري الدخول..." : "دخول"}
                        </Button>
                    </form>
                    <p className="mt-6 text-center text-white/60 text-sm font-body">
                        لا تملك حساب؟ <Link data-testid="goto-register-link" to="/register" className="text-[hsl(355,93%,60%)] hover:underline">أنشئ حساب</Link>
                    </p>
                </div>
            </div>
        </div>
    );
}
