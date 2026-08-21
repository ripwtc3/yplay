import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { toast } from "sonner";
import { Skull } from "lucide-react";

export default function Register() {
    const [form, setForm] = useState({ username: "", display_name: "", email: "", password: "", confirm: "" });
    const [busy, setBusy] = useState(false);
    const { register } = useAuth();
    const nav = useNavigate();

    const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });

    const submit = async (e) => {
        e.preventDefault();
        if (form.password !== form.confirm) { toast.error("كلمات المرور غير متطابقة"); return; }
        if (form.password.length < 6) { toast.error("كلمة المرور قصيرة (6 أحرف على الأقل)"); return; }
        setBusy(true);
        try {
            await register({ username: form.username, display_name: form.display_name, email: form.email, password: form.password });
            toast.success("مرحباً بك! تم إنشاء الحساب");
            nav("/dashboard");
        } catch (err) {
            toast.error(err.response?.data?.detail || "فشل إنشاء الحساب");
        } finally { setBusy(false); }
    };

    return (
        <div className="min-h-screen grid place-items-center px-6 py-12 noise-bg">
            <div className="w-full max-w-md">
                <div className="flex items-center gap-3 mb-8 font-display">
                    <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-[hsl(355,93%,46%)] to-[hsl(355,93%,26%)] grid place-items-center">
                        <Skull className="w-5 h-5 text-white" />
                    </div>
                    <span className="text-2xl font-extrabold">لايف <span className="text-[hsl(355,93%,60%)]">ألعاب</span></span>
                </div>
                <div className="rounded-2xl border border-white/10 bg-card p-8 fade-in-up">
                    <h1 className="font-display text-3xl font-extrabold mb-2">أنشئ حسابك</h1>
                    <p className="text-white/60 mb-6 font-body">دقيقة واحدة وتقدر تلعب مع أصحابك</p>
                    <form onSubmit={submit} className="space-y-4">
                        <div>
                            <Label className="font-body">اسم المستخدم</Label>
                            <Input data-testid="register-username-input" value={form.username} onChange={set("username")} required minLength={3} maxLength={24} className="mt-2 h-11 bg-black/40 border-white/10" />
                        </div>
                        <div>
                            <Label className="font-body">الاسم المعروض</Label>
                            <Input data-testid="register-displayname-input" value={form.display_name} onChange={set("display_name")} required minLength={2} maxLength={32} className="mt-2 h-11 bg-black/40 border-white/10" />
                        </div>
                        <div>
                            <Label className="font-body">البريد الإلكتروني</Label>
                            <Input data-testid="register-email-input" type="email" value={form.email} onChange={set("email")} required className="mt-2 h-11 bg-black/40 border-white/10" />
                        </div>
                        <div className="grid grid-cols-2 gap-3">
                            <div>
                                <Label className="font-body">كلمة المرور</Label>
                                <Input data-testid="register-password-input" type="password" value={form.password} onChange={set("password")} required minLength={6} className="mt-2 h-11 bg-black/40 border-white/10" />
                            </div>
                            <div>
                                <Label className="font-body">تأكيد كلمة المرور</Label>
                                <Input data-testid="register-confirm-input" type="password" value={form.confirm} onChange={set("confirm")} required minLength={6} className="mt-2 h-11 bg-black/40 border-white/10" />
                            </div>
                        </div>
                        <Button data-testid="register-submit-btn" type="submit" disabled={busy} className="w-full h-12 font-display font-bold text-base bg-[hsl(355,93%,46%)] hover:bg-[hsl(355,93%,40%)] transition-colors">
                            {busy ? "جاري..." : "إنشاء حساب"}
                        </Button>
                    </form>
                    <p className="mt-6 text-center text-white/60 text-sm font-body">
                        لديك حساب؟ <Link data-testid="goto-login-link" to="/login" className="text-[hsl(355,93%,60%)] hover:underline">دخول</Link>
                    </p>
                </div>
            </div>
        </div>
    );
}
