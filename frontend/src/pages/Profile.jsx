import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { toast } from "sonner";
import { Link2, Trash2, ArrowRight, Twitch, Youtube, Video } from "lucide-react";

const PROVIDERS = [
    { key: "twitch", label: "Twitch", color: "hsl(280,100%,70%)", icon: Twitch, placeholder: "اسم قناتك (بدون @)" },
    { key: "youtube", label: "YouTube", color: "hsl(0,90%,55%)", icon: Youtube, placeholder: "@handle" },
    { key: "tiktok", label: "TikTok", color: "hsl(340,90%,60%)", icon: Video, placeholder: "@username" },
    { key: "kick", label: "Kick", color: "hsl(120,80%,45%)", icon: Video, placeholder: "username" },
];

export default function Profile() {
    const nav = useNavigate();
    const { user } = useAuth();
    const [accounts, setAccounts] = useState([]);
    const [loading, setLoading] = useState(true);
    const [selectedProvider, setSelectedProvider] = useState("twitch");
    const [handle, setHandle] = useState("");
    const [displayName, setDisplayName] = useState("");
    const [busy, setBusy] = useState(false);

    const load = async () => {
        setLoading(true);
        try {
            const r = await api.get("/users/me/connected-accounts");
            setAccounts(r.data.accounts || []);
        } catch (e) { /* ignore */ }
        finally { setLoading(false); }
    };

    useEffect(() => { load(); }, []);

    const add = async (e) => {
        e.preventDefault();
        if (!handle.trim()) return;
        setBusy(true);
        try {
            await api.post("/users/me/connected-accounts", {
                provider: selectedProvider,
                provider_username: handle,
                display_name: displayName || undefined,
            });
            toast.success("تم ربط الحساب");
            setHandle(""); setDisplayName("");
            load();
        } catch (err) {
            toast.error(err.response?.data?.detail || "فشل الربط");
        } finally { setBusy(false); }
    };

    const remove = async (id) => {
        try {
            await api.delete(`/users/me/connected-accounts/${id}`);
            toast.success("تم الفصل");
            load();
        } catch (err) {
            toast.error("خطأ");
        }
    };

    const provOf = (k) => PROVIDERS.find((p) => p.key === k) || PROVIDERS[0];

    return (
        <div className="min-h-screen">
            <div className="max-w-3xl mx-auto px-6 py-12">
                <button data-testid="back-btn" onClick={() => nav(-1)} className="text-white/60 hover:text-white mb-6 font-body flex items-center gap-2">
                    <ArrowRight className="w-4 h-4" /> رجوع
                </button>
                <h1 className="font-display text-4xl font-extrabold mb-2">حسابي</h1>
                <p className="text-white/60 font-body mb-8">
                    مرحباً <span className="text-white">{user?.display_name}</span> · <span className="text-white/40">@{user?.username}</span>
                </p>

                {/* Connected Accounts */}
                <div className="rounded-2xl border border-white/10 bg-card p-6 fade-in-up">
                    <div className="flex items-center gap-2 mb-2">
                        <Link2 className="w-5 h-5 text-[hsl(355,93%,60%)]" />
                        <h3 className="font-display text-xl font-bold">حسابات البث المرتبطة</h3>
                    </div>
                    <p className="text-white/60 text-sm font-body mb-6">اربط حساباتك على منصات البث ليتعرف عليك جمهورك داخل لعبة Mafia</p>

                    {loading ? (
                        <div className="text-white/50 font-body">جاري التحميل...</div>
                    ) : accounts.length === 0 ? (
                        <div className="text-white/40 text-center py-6 font-body">لا توجد حسابات مربوطة بعد</div>
                    ) : (
                        <div className="space-y-2 mb-6">
                            {accounts.map((a) => {
                                const p = provOf(a.provider);
                                const Icon = p.icon;
                                return (
                                    <div key={a.id} data-testid={`account-${a.provider}`} className="flex items-center justify-between rounded-xl border border-white/10 bg-black/30 p-3">
                                        <div className="flex items-center gap-3">
                                            <div className="w-10 h-10 rounded-lg grid place-items-center" style={{ background: `${p.color}20`, border: `1px solid ${p.color}40` }}>
                                                <Icon className="w-5 h-5" style={{ color: p.color }} />
                                            </div>
                                            <div>
                                                <div className="font-body font-bold">{p.label}</div>
                                                <a href={a.channel_url} target="_blank" rel="noopener noreferrer" className="text-xs text-white/50 hover:text-white/80 font-body">@{a.provider_username}</a>
                                            </div>
                                        </div>
                                        <button data-testid={`remove-account-${a.provider}`} onClick={() => remove(a.id)} className="p-2 rounded-lg border border-red-500/30 hover:bg-red-500/10 transition-colors">
                                            <Trash2 className="w-4 h-4 text-red-400" />
                                        </button>
                                    </div>
                                );
                            })}
                        </div>
                    )}

                    {/* Add form */}
                    <form onSubmit={add} className="border-t border-white/10 pt-6 space-y-4">
                        <div className="text-sm font-body font-bold text-white/80">ربط حساب جديد</div>
                        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                            {PROVIDERS.map((p) => {
                                const Icon = p.icon;
                                const active = selectedProvider === p.key;
                                const already = accounts.some((a) => a.provider === p.key);
                                return (
                                    <button
                                        key={p.key}
                                        type="button"
                                        data-testid={`select-provider-${p.key}`}
                                        onClick={() => setSelectedProvider(p.key)}
                                        disabled={already}
                                        className={`rounded-xl border p-3 flex flex-col items-center gap-1 transition-colors ${
                                            active ? "border-white/40 bg-white/5" : "border-white/10 hover:border-white/30"
                                        } ${already ? "opacity-40 cursor-not-allowed" : ""}`}
                                    >
                                        <Icon className="w-5 h-5" style={{ color: p.color }} />
                                        <span className="text-xs font-body">{p.label}</span>
                                        {already && <span className="text-[10px] text-emerald-400">مربوط</span>}
                                    </button>
                                );
                            })}
                        </div>
                        <div>
                            <Label className="font-body text-sm">اسم القناة أو المعرّف</Label>
                            <Input
                                data-testid="handle-input"
                                value={handle}
                                onChange={(e) => setHandle(e.target.value)}
                                placeholder={provOf(selectedProvider).placeholder}
                                required
                                className="mt-2 h-11 bg-black/40 border-white/10"
                            />
                        </div>
                        <div>
                            <Label className="font-body text-sm">الاسم المعروض (اختياري)</Label>
                            <Input
                                data-testid="displayname-input"
                                value={displayName}
                                onChange={(e) => setDisplayName(e.target.value)}
                                placeholder="اسم قناتك الكامل"
                                className="mt-2 h-11 bg-black/40 border-white/10"
                            />
                        </div>
                        <Button data-testid="link-account-btn" type="submit" disabled={busy} className="w-full h-11 font-display font-bold bg-[hsl(355,93%,46%)] hover:bg-[hsl(355,93%,40%)]">
                            {busy ? "جاري..." : "ربط الحساب"}
                        </Button>
                        <div className="text-xs text-white/40 font-body text-center">
                            🔒 لا نطلب كلمة مرور — فقط اسم القناة العام. OAuth رسمي قادم قريباً.
                        </div>
                    </form>
                </div>
            </div>
        </div>
    );
}
