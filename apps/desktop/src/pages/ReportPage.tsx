import { type ChangeEvent, useCallback, useEffect, useMemo, useState } from "react";
import { API_BASE, apiUrl } from "../lib/apiBase";
import { noteService } from "../lib/noteService";

type AnalyzeMode = "idle" | "running" | "success" | "error";

const DEFAULT_PROJECT = "sophia";

function parseErrorText(raw: string): string {
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

export function ReportPage() {
    const [projectName, setProjectName] = useState(DEFAULT_PROJECT);
    const [riskThreshold, setRiskThreshold] = useState("0.8");
    const [sourcePath, setSourcePath] = useState("");
    const [target, setTarget] = useState("spec-module");
    const [change, setChange] = useState("문서 변경 검토");
    const [scope, setScope] = useState("");
    const [mode, setMode] = useState<AnalyzeMode>("idle");
    const [message, setMessage] = useState("현황판 준비됨");
    const [refreshSeed, setRefreshSeed] = useState(Date.now());

    const dashboardSrc = useMemo(
        () => `${API_BASE}/dashboard/?t=${refreshSeed}`,
        [refreshSeed],
    );

    const refreshCanopy = useCallback(async () => {
        setMode("running");
        setMessage("현황판 내보내기 실행 중...");
        const threshold = Number.parseFloat(riskThreshold);
        const query = Number.isFinite(threshold) ? `?risk_threshold=${threshold}` : "";
        const endpoint = apiUrl(`/forest/projects/${encodeURIComponent(projectName)}/canopy/export${query}`);
        try {
            const response = await fetch(endpoint, { method: "POST" });
            if (!response.ok) {
                const errText = await response.text();
                throw new Error(parseErrorText(errText));
            }
            setRefreshSeed(Date.now());
            setMode("success");
            setMessage("현황판 갱신 완료");
        } catch (error) {
            setMode("error");
            setMessage(`현황판 갱신 실패: ${String(error)}`);
        }
    }, [projectName, riskThreshold]);

    useEffect(() => {
        refreshCanopy();
    }, [refreshCanopy]);

    const runAnalyzeByPath = useCallback(async () => {
        const trimmedPath = sourcePath.trim();
        if (!trimmedPath) {
            setMode("error");
            setMessage("분석할 파일 경로를 입력해주세요.");
            return;
        }

        setMode("running");
        setMessage("파일 기반 SonE 분석 실행 중...");
        const endpoint = apiUrl(`/forest/projects/${encodeURIComponent(projectName)}/grove/analyze/path`);
        const payload = {
            path: trimmedPath,
            target: target.trim() || "spec-module",
            change: change.trim() || "문서 변경 검토",
            scope: scope.trim() || null,
        };

        try {
            const response = await fetch(endpoint, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload),
            });
            if (!response.ok) {
                const errText = await response.text();
                throw new Error(parseErrorText(errText));
            }
            setMode("success");
            setMessage("파일 SonE 검증 완료. 현황판 갱신 중...");
            await refreshCanopy();
        } catch (error) {
            setMode("error");
            setMessage(`파일 분석 실패: ${String(error)}`);
        }
    }, [sourcePath, projectName, target, change, scope, refreshCanopy]);

    const runAnalyzeTodayEditorFile = useCallback(async () => {
        const todayPath = noteService.getTodayFileName();
        setSourcePath(todayPath);
        setMode("running");
        setMessage(`오늘 에디터 파일 분석 준비: ${todayPath}`);

        const endpoint = apiUrl(`/forest/projects/${encodeURIComponent(projectName)}/grove/analyze/path`);
        const payload = {
            path: todayPath,
            target: target.trim() || "spec-module",
            change: change.trim() || "문서 변경 검토",
            scope: scope.trim() || null,
        };

        try {
            const response = await fetch(endpoint, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload),
            });
            if (!response.ok) {
                const errText = await response.text();
                throw new Error(parseErrorText(errText));
            }
            setMode("success");
            setMessage("에디터 파일 SonE 검증 완료. 현황판 갱신 중...");
            await refreshCanopy();
        } catch (error) {
            setMode("error");
            setMessage(`에디터 파일 분석 실패: ${String(error)}`);
        }
    }, [projectName, target, change, scope, refreshCanopy]);

    const runAnalyzeByUpload = useCallback(
        async (event: ChangeEvent<HTMLInputElement>) => {
            const file = event.target.files?.[0];
            if (!file) return;

            setMode("running");
            setMessage(`업로드 파일 분석 중: ${file.name}`);

            try {
                const content = await file.text();
                const endpoint = apiUrl(`/forest/projects/${encodeURIComponent(projectName)}/grove/analyze`);
                const response = await fetch(endpoint, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        doc_name: file.name,
                        content,
                        target: target.trim() || "spec-module",
                        change: change.trim() || "문서 변경 검토",
                        scope: scope.trim() || null,
                    }),
                });
                if (!response.ok) {
                    const errText = await response.text();
                    throw new Error(parseErrorText(errText));
                }
                setMode("success");
                setMessage("업로드 문서 SonE 검증 완료. 현황판 갱신 중...");
                await refreshCanopy();
            } catch (error) {
                setMode("error");
                setMessage(`업로드 분석 실패: ${String(error)}`);
            } finally {
                event.target.value = "";
            }
        },
        [projectName, target, change, scope, refreshCanopy],
    );

    const modeColor =
        mode === "error"
            ? "text-red-300"
            : mode === "success"
              ? "text-emerald-300"
              : mode === "running"
                ? "text-amber-300"
                : "text-gray-300";

    return (
        <div className="h-full w-full bg-[#0b1020] text-gray-200 flex flex-col">
            <div className="px-4 py-3 border-b border-[#263246] bg-[#111827] flex items-center justify-between gap-3">
                <div>
                    <h1 className="text-sm font-semibold text-gray-100">Sophia Forest · 현황판</h1>
                    <p className="text-xs text-gray-400 mt-0.5">설계 검토(SonE) 기반 진행 상태 관제</p>
                </div>
                <button
                    onClick={refreshCanopy}
                    className="px-3 py-1.5 text-xs rounded-md border border-[#334155] bg-[#1f2937] hover:bg-[#273449]"
                >
                    현황판 새로고침
                </button>
            </div>

            <div className="flex-1 min-h-0 grid grid-cols-[340px_minmax(0,1fr)] gap-0">
                <div className="border-r border-[#263246] bg-[#0f172a] p-3 overflow-auto">
                    <div className="space-y-3">
                        <div className="rounded-lg border border-[#334155] bg-[#111827] p-3">
                            <p className="text-xs text-gray-400 mb-2">프로젝트 / 리스크 임계값</p>
                            <label className="text-xs text-gray-300 block mb-1">Project</label>
                            <input
                                value={projectName}
                                onChange={(event) => setProjectName(event.target.value)}
                                className="w-full rounded bg-[#0b1220] border border-[#334155] px-2 py-1.5 text-xs"
                            />
                            <label className="text-xs text-gray-300 block mt-2 mb-1">Risk Threshold</label>
                            <input
                                value={riskThreshold}
                                onChange={(event) => setRiskThreshold(event.target.value)}
                                className="w-full rounded bg-[#0b1220] border border-[#334155] px-2 py-1.5 text-xs"
                            />
                        </div>

                        <div className="rounded-lg border border-[#334155] bg-[#111827] p-3">
                            <p className="text-xs text-gray-400 mb-2">SonE 검증 입력</p>
                            <label className="text-xs text-gray-300 block mb-1">Target</label>
                            <input
                                value={target}
                                onChange={(event) => setTarget(event.target.value)}
                                className="w-full rounded bg-[#0b1220] border border-[#334155] px-2 py-1.5 text-xs"
                            />
                            <label className="text-xs text-gray-300 block mt-2 mb-1">Change</label>
                            <input
                                value={change}
                                onChange={(event) => setChange(event.target.value)}
                                className="w-full rounded bg-[#0b1220] border border-[#334155] px-2 py-1.5 text-xs"
                            />
                            <label className="text-xs text-gray-300 block mt-2 mb-1">Scope (optional)</label>
                            <input
                                value={scope}
                                onChange={(event) => setScope(event.target.value)}
                                className="w-full rounded bg-[#0b1220] border border-[#334155] px-2 py-1.5 text-xs"
                            />
                        </div>

                        <div className="rounded-lg border border-[#334155] bg-[#111827] p-3">
                            <p className="text-xs text-gray-400 mb-2">A. 저장 파일 경로로 분석</p>
                            <input
                                value={sourcePath}
                                onChange={(event) => setSourcePath(event.target.value)}
                                placeholder="/Users/.../something.md"
                                className="w-full rounded bg-[#0b1220] border border-[#334155] px-2 py-1.5 text-xs"
                            />
                            <div className="flex gap-2 mt-2">
                                <button
                                    onClick={runAnalyzeByPath}
                                    className="flex-1 px-2 py-1.5 text-xs rounded-md border border-[#3b82f6] bg-[#1d4ed8] hover:bg-[#2563eb]"
                                >
                                    파일 분석 실행
                                </button>
                                <button
                                    onClick={runAnalyzeTodayEditorFile}
                                    className="px-2 py-1.5 text-xs rounded-md border border-[#334155] bg-[#1f2937] hover:bg-[#273449]"
                                >
                                    오늘 노트
                                </button>
                            </div>
                        </div>

                        <div className="rounded-lg border border-[#334155] bg-[#111827] p-3">
                            <p className="text-xs text-gray-400 mb-2">B. 업로드 파일로 분석</p>
                            <label className="w-full inline-flex items-center justify-center px-2 py-1.5 text-xs rounded-md border border-[#334155] bg-[#1f2937] hover:bg-[#273449] cursor-pointer">
                                .md/.txt 파일 선택
                                <input
                                    type="file"
                                    accept=".md,.markdown,.txt,text/markdown,text/plain"
                                    onChange={runAnalyzeByUpload}
                                    className="hidden"
                                />
                            </label>
                        </div>

                        <div className="rounded-lg border border-[#334155] bg-[#111827] p-3">
                            <p className="text-xs text-gray-400 mb-1">실행 상태</p>
                            <p className={`text-xs ${modeColor}`}>{message}</p>
                        </div>
                    </div>
                </div>

                <div className="min-w-0 min-h-0 bg-[#0b1020]">
                    <iframe
                        src={dashboardSrc}
                        className="w-full h-full border-none"
                        title="Sophia Forest Dashboard"
                    />
                </div>
            </div>
        </div>
    );
}
