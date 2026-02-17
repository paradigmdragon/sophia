import type { ChangeEvent } from "react";

import type { EventFilter, ModuleSort } from "./types";

type ControlPanelProps = {
    projectName: string;
    onProjectNameChange: (value: string) => void;
    riskThreshold: string;
    onRiskThresholdChange: (value: string) => void;
    moduleSort: ModuleSort;
    onModuleSortChange: (value: ModuleSort) => void;
    eventFilter: EventFilter;
    onEventFilterChange: (value: EventFilter) => void;
    sourcePath: string;
    onSourcePathChange: (value: string) => void;
    target: string;
    onTargetChange: (value: string) => void;
    change: string;
    onChangeTextChange: (value: string) => void;
    scope: string;
    onScopeChange: (value: string) => void;
    onAnalyzeByPath: () => void;
    onAnalyzeTodayEditorFile: () => void;
    onAnalyzeByUpload: (event: ChangeEvent<HTMLInputElement>) => void;
    modeColor: string;
    message: string;
};

export function ControlPanel({
    projectName,
    onProjectNameChange,
    riskThreshold,
    onRiskThresholdChange,
    moduleSort,
    onModuleSortChange,
    eventFilter,
    onEventFilterChange,
    sourcePath,
    onSourcePathChange,
    target,
    onTargetChange,
    change,
    onChangeTextChange,
    scope,
    onScopeChange,
    onAnalyzeByPath,
    onAnalyzeTodayEditorFile,
    onAnalyzeByUpload,
    modeColor,
    message,
}: ControlPanelProps) {
    return (
        <div className="border-r border-[#263246] bg-[#0f172a] p-3 overflow-auto">
            <div className="space-y-3">
                <div className="rounded-lg border border-[#334155] bg-[#111827] p-3">
                    <p className="text-xs text-gray-400 mb-2">프로젝트 / 리스크 임계값</p>
                    <label className="text-xs text-gray-300 block mb-1">Project</label>
                    <input
                        value={projectName}
                        onChange={(event) => onProjectNameChange(event.target.value)}
                        className="w-full rounded bg-[#0b1220] border border-[#334155] px-2 py-1.5 text-xs"
                    />
                    <label className="text-xs text-gray-300 block mt-2 mb-1">Risk Threshold</label>
                    <input
                        value={riskThreshold}
                        onChange={(event) => onRiskThresholdChange(event.target.value)}
                        className="w-full rounded bg-[#0b1220] border border-[#334155] px-2 py-1.5 text-xs"
                    />
                    <label className="text-xs text-gray-300 block mt-2 mb-1">Module Sort</label>
                    <select
                        value={moduleSort}
                        onChange={(event) => onModuleSortChange(event.target.value as ModuleSort)}
                        className="w-full rounded bg-[#0b1220] border border-[#334155] px-2 py-1.5 text-xs"
                    >
                        <option value="importance">중요도 순</option>
                        <option value="progress">진행률 순</option>
                        <option value="risk">리스크 순</option>
                    </select>
                    <label className="text-xs text-gray-300 block mt-2 mb-1">Event Filter</label>
                    <select
                        value={eventFilter}
                        onChange={(event) => onEventFilterChange(event.target.value as EventFilter)}
                        className="w-full rounded bg-[#0b1220] border border-[#334155] px-2 py-1.5 text-xs"
                    >
                        <option value="all">전체 이벤트</option>
                        <option value="analysis">분석 이벤트</option>
                        <option value="work">작업 이벤트</option>
                        <option value="canopy">현황판 이벤트</option>
                        <option value="question">질문 이벤트</option>
                    </select>
                </div>

                <div className="rounded-lg border border-[#334155] bg-[#111827] p-3">
                    <p className="text-xs text-gray-400 mb-2">SonE 검증 입력</p>
                    <label className="text-xs text-gray-300 block mb-1">Target</label>
                    <input
                        value={target}
                        onChange={(event) => onTargetChange(event.target.value)}
                        className="w-full rounded bg-[#0b1220] border border-[#334155] px-2 py-1.5 text-xs"
                    />
                    <label className="text-xs text-gray-300 block mt-2 mb-1">Change</label>
                    <input
                        value={change}
                        onChange={(event) => onChangeTextChange(event.target.value)}
                        className="w-full rounded bg-[#0b1220] border border-[#334155] px-2 py-1.5 text-xs"
                    />
                    <label className="text-xs text-gray-300 block mt-2 mb-1">Scope (optional)</label>
                    <input
                        value={scope}
                        onChange={(event) => onScopeChange(event.target.value)}
                        className="w-full rounded bg-[#0b1220] border border-[#334155] px-2 py-1.5 text-xs"
                    />
                </div>

                <div className="rounded-lg border border-[#334155] bg-[#111827] p-3">
                    <p className="text-xs text-gray-400 mb-2">A. 저장 파일 경로로 분석</p>
                    <input
                        value={sourcePath}
                        onChange={(event) => onSourcePathChange(event.target.value)}
                        placeholder="/Users/.../something.md"
                        className="w-full rounded bg-[#0b1220] border border-[#334155] px-2 py-1.5 text-xs"
                    />
                    <div className="flex gap-2 mt-2">
                        <button
                            onClick={onAnalyzeByPath}
                            className="flex-1 px-2 py-1.5 text-xs rounded-md border border-[#3b82f6] bg-[#1d4ed8] hover:bg-[#2563eb]"
                        >
                            파일 분석 실행
                        </button>
                        <button
                            onClick={onAnalyzeTodayEditorFile}
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
                            onChange={onAnalyzeByUpload}
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
    );
}
