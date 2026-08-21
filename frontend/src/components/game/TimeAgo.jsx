import { useEffect, useState } from "react";

// "قبل X ثانية / دقيقة / ساعة" — updates every 30s
export default function TimeAgo({ iso }) {
    const [tick, setTick] = useState(0);
    useEffect(() => {
        const t = setInterval(() => setTick((x) => x + 1), 30_000);
        return () => clearInterval(t);
    }, []);
    if (!iso) return null;
    const seconds = Math.max(0, Math.floor((Date.now() - new Date(iso).getTime()) / 1000));
    let label;
    if (seconds < 5) label = "الآن";
    else if (seconds < 60) label = `قبل ${seconds} ث`;
    else if (seconds < 3600) label = `قبل ${Math.floor(seconds / 60)} د`;
    else if (seconds < 86400) label = `قبل ${Math.floor(seconds / 3600)} س`;
    else label = new Date(iso).toLocaleDateString("ar");
    // suppress warning
    // eslint-disable-next-line
    const _ = tick;
    return <span className="text-[10px] text-white/40 font-body ms-2">{label}</span>;
}
