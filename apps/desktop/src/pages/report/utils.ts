export function parseErrorText(raw: string): string {
    if (!raw) return "요청 실패";
    try {
        const parsed = JSON.parse(raw);
        if (typeof parsed?.detail === "string") return parsed.detail;
        if (parsed?.detail && typeof parsed.detail === "object") {
            const code = String((parsed.detail as { code?: string }).code || "").trim().toUpperCase();
            const message = String((parsed.detail as { message?: string }).message || "").trim();
            if (code) {
                const mapped = mapApiErrorCodeToText(code);
                if (mapped) return mapped;
            }
            if (message) return message;
        }
        if (typeof parsed?.message === "string") return parsed.message;
    } catch {
        // noop
    }
    return raw;
}

function mapApiErrorCodeToText(code: string): string {
    const mapping: Record<string, string> = {
        CANDIDATE_EPISODE_MISMATCH: "선택한 후보가 현재 에피소드와 일치하지 않습니다. 목록을 새로고침 후 다시 시도해 주세요.",
        CANDIDATE_ALREADY_ADOPTED: "이미 채택된 후보입니다.",
        CANDIDATE_ALREADY_REJECTED: "이미 거절된 후보입니다.",
        ADOPT_INVALID: "후보 채택 요청이 유효하지 않습니다.",
        REJECT_INVALID: "후보 거절 요청이 유효하지 않습니다.",
    };
    return mapping[code] || "";
}

export function inferModuleFromNode(value: string | undefined): string {
    const raw = String(value || "").trim().toLowerCase();
    if (!raw) return "forest";
    if (raw.includes("bitmap") || raw.includes("validator") || raw.includes("engine") || raw.includes("core")) return "core";
    if (raw.includes("chat") || raw.includes("dialog") || raw.includes("conversation")) return "chat";
    if (raw.includes("note") || raw.includes("memo")) return "note";
    if (raw.includes("editor") || raw.includes("doc") || raw.includes("spec") || raw.includes(".md")) return "editor";
    if (raw.includes("subtitle") || raw.includes("caption") || raw.includes("srt")) return "subtitle";
    return "forest";
}
