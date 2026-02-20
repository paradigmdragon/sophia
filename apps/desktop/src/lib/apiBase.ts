const DEFAULT_API_BASE = "http://127.0.0.1:8090";

function normalizeLocalhost(value: string): string {
    const raw = value.trim();
    if (!raw) return DEFAULT_API_BASE;
    try {
        const parsed = new URL(raw);
        if (parsed.hostname.toLowerCase() === "localhost") {
            parsed.hostname = "127.0.0.1";
        }
        return parsed.toString().replace(/\/$/, "");
    } catch {
        return DEFAULT_API_BASE;
    }
}

const envBase = typeof import.meta !== "undefined"
    ? (import.meta as any)?.env?.VITE_API_BASE_URL
    : "";

export const API_BASE = normalizeLocalhost(String(envBase || DEFAULT_API_BASE));

export function apiUrl(path: string): string {
    const suffix = path.startsWith("/") ? path : `/${path}`;
    return `${API_BASE}${suffix}`;
}
