/** Formatting helpers shared across SGC dashboard components. */

const COMPACT = [
    { limit: 1e12, suffix: "T" },
    { limit: 1e9,  suffix: "B" },
    { limit: 1e6,  suffix: "M" },
    { limit: 1e3,  suffix: "K" },
];

export function compactNumber(value, decimals = 1) {
    const n = Number(value) || 0;
    const abs = Math.abs(n);
    for (const { limit, suffix } of COMPACT) {
        if (abs >= limit) {
            return `${(n / limit).toFixed(decimals).replace(/\.0$/, "")}${suffix}`;
        }
    }
    return n.toLocaleString(undefined, { maximumFractionDigits: decimals });
}

export function formatValue(value, format, currency) {
    const n = Number(value) || 0;
    if (format === "percent") {
        return `${n.toFixed(1)}%`;
    }
    if (format === "currency") {
        const body = compactNumber(n);
        const sym = (currency && currency.symbol) || "";
        return currency && currency.position === "after" ? `${body} ${sym}` : `${sym}${body}`;
    }
    if (format === "duration") {
        return `${n.toFixed(0)} min`;
    }
    return compactNumber(n, 0);
}

/** Accent token -> concrete colour, read from the CSS custom properties. */
export function accentColor(accent) {
    const map = {
        brand: "--sgc-brand-500",
        teal: "--sgc-teal-500",
        amber: "--sgc-amber-500",
        violet: "--sgc-violet-500",
        rose: "--sgc-rose-500",
        slate: "--sgc-slate-500",
    };
    const varName = map[accent] || map.brand;
    return getComputedStyle(document.documentElement)
        .getPropertyValue(varName).trim() || "#0A1B30";
}

export function paletteFor(accent, count) {
    const base = [
        accentColor(accent),
        accentColor("teal"),
        accentColor("violet"),
        accentColor("amber"),
        accentColor("rose"),
        accentColor("slate"),
    ];
    return Array.from({ length: count }, (_, i) => base[i % base.length]);
}

/** Convert #RRGGBB to rgba() with the given alpha. */
export function withAlpha(hex, alpha) {
    const h = hex.replace("#", "");
    const full = h.length === 3 ? h.split("").map((c) => c + c).join("") : h;
    const num = parseInt(full, 16);
    return `rgba(${(num >> 16) & 255}, ${(num >> 8) & 255}, ${num & 255}, ${alpha})`;
}
