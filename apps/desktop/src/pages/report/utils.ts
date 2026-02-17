export function parseErrorText(raw: string): string {
    if (!raw) return "요청 실패";
    try {
        const parsed = JSON.parse(raw);
        if (typeof parsed?.detail === "string") return parsed.detail;
        if (typeof parsed?.message === "string") return parsed.message;
    } catch {
        // noop
    }
    return raw;
}

export function inferModuleFromNode(value: string | undefined): string {
    const raw = String(value || "").trim().toLowerCase();
    if (!raw) return "forest";
    if (raw.includes("chat") || raw.includes("dialog") || raw.includes("conversation")) return "chat";
    if (raw.includes("note") || raw.includes("memo")) return "note";
    if (raw.includes("editor") || raw.includes("doc") || raw.includes("spec") || raw.includes(".md")) return "editor";
    if (raw.includes("subtitle") || raw.includes("caption") || raw.includes("srt")) return "subtitle";
    return "forest";
}
