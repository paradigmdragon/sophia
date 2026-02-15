import { useEffect, useMemo } from "react";
import { API_BASE, apiUrl } from "../lib/apiBase";

export function ReportPage() {
    useEffect(() => {
        fetch(apiUrl("/forest/projects/sophia/canopy/export"), {
            method: "POST",
        }).catch((error) => {
            console.error("Failed to render canopy dashboard:", error);
        });
    }, []);

    const src = useMemo(() => `${API_BASE}/dashboard/?t=${Date.now()}`, []);

    return (
        <div className="flex flex-col h-full w-full bg-[#111]">
            <iframe
                src={src}
                className="w-full h-full border-none"
                title="Sophia Forest"
            />
        </div>
    );
}
