import type { ChangeEvent } from "react";

import type { EventFilter, ForestModule, ModuleSort } from "./types";

type ControlPanelProps = {
    projectName: string;
    onProjectNameChange: (value: string) => void;
    riskThreshold: string;
    onRiskThresholdChange: (value: string) => void;
    moduleSort: ModuleSort;
    onModuleSortChange: (value: ModuleSort) => void;
    eventFilter: EventFilter;
    onEventFilterChange: (value: EventFilter) => void;
    serverModuleFilter: ForestModule;
    onServerModuleFilterChange: (value: ForestModule) => void;
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
    onSyncProjectStatus: () => void;
    modeColor: string;
    message: string;
    pageStatusText: string;
    canGoPrevPage: boolean;
    canGoNextPage: boolean;
    onPrevPage: () => void;
    onNextPage: () => void;
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
    serverModuleFilter,
    onServerModuleFilterChange,
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
    onSyncProjectStatus,
    modeColor,
    message,
    pageStatusText,
    canGoPrevPage,
    canGoNextPage,
    onPrevPage,
    onNextPage,
}: ControlPanelProps) {
    return (
        <div className="border-r border-[#263246] bg-[#0f172a] p-3 overflow-auto">
            <div className="space-y-3">
                <div className="rounded-lg border border-[#334155] bg-[#111827] p-3">
                    <p className="text-xs text-gray-400 mb-2">빠른 실행</p>
                    <button
                        onClick={onSyncProjectStatus}
                        className="w-full px-2 py-1.5 text-xs rounded-md border border-emerald-400 bg-emerald-900/20 hover:bg-emerald-900/35 text-emerald-100"
                    >
                        진행상태 동기화 (Forest 반영)
                    </button>
                    <div className="grid grid-cols-2 gap-2 mt-2">
                        <button
                            onClick={onAnalyzeTodayEditorFile}
                            className="px-2 py-1.5 text-xs rounded-md border border-[#334155] bg-[#1f2937] hover:bg-[#273449]"
                        >
                            오늘 노트 분석
                        </button>
                        <button
                            onClick={onAnalyzeByPath}
                            className="px-2 py-1.5 text-xs rounded-md border border-[#3b82f6] bg-[#1d4ed8] hover:bg-[#2563eb]"
                        >
                            경로 분석 실행
                        </button>
                    </div>
                    <div className="mt-2 rounded border border-[#334155] bg-[#0b1220] px-2 py-2">
                        <p className="text-[11px] text-gray-400">실행 상태</p>
                        <p className={`text-[11px] ${modeColor}`}>{message}</p>
                        <p className="text-[11px] text-gray-500 mt-1">페이지: {pageStatusText}</p>
                    </div>
                </div>

                <div className="rounded-lg border border-[#334155] bg-[#111827] p-3">
                    <p className="text-xs text-gray-400 mb-2">긴급 필터</p>
                    <label className="text-xs text-gray-300 block mb-1">Risk Threshold</label>
                    <input
                        value={riskThreshold}
                        onChange={(event) => onRiskThresholdChange(event.target.value)}
                        className="w-full rounded bg-[#0b1220] border border-[#334155] px-2 py-1.5 text-xs"
                    />
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
                        <option value="bitmap">비트맵 이벤트</option>
                    </select>
                    <label className="text-xs text-gray-300 block mt-2 mb-1">Module Filter</label>
                    <select
                        value={serverModuleFilter}
                        onChange={(event) => onServerModuleFilterChange(event.target.value as ForestModule)}
                        className="w-full rounded bg-[#0b1220] border border-[#334155] px-2 py-1.5 text-xs"
                    >
                        <option value="all">전체 모듈</option>
                        <option value="chat">채팅</option>
                        <option value="note">노트</option>
                        <option value="editor">에디터</option>
                        <option value="subtitle">자막</option>
                        <option value="core">코어</option>
                        <option value="forest">소피아 숲</option>
                    </select>
                </div>

                <details className="rounded-lg border border-[#334155] bg-[#111827] p-3" open>
                    <summary className="cursor-pointer text-xs text-gray-300 select-none">SonE 분석 입력 (핵심)</summary>
                    <div className="mt-2">
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
                        <label className="text-xs text-gray-300 block mt-2 mb-1">Source Path</label>
                        <input
                            value={sourcePath}
                            onChange={(event) => onSourcePathChange(event.target.value)}
                            placeholder="/Users/.../something.md"
                            className="w-full rounded bg-[#0b1220] border border-[#334155] px-2 py-1.5 text-xs"
                        />
                        <label className="w-full inline-flex items-center justify-center px-2 py-1.5 text-xs rounded-md border border-[#334155] bg-[#1f2937] hover:bg-[#273449] cursor-pointer mt-2">
                            .md/.txt 파일 선택
                            <input
                                type="file"
                                accept=".md,.markdown,.txt,text/markdown,text/plain"
                                onChange={onAnalyzeByUpload}
                                className="hidden"
                            />
                        </label>
                    </div>
                </details>

                <details className="rounded-lg border border-[#334155] bg-[#111827] p-3">
                    <summary className="cursor-pointer text-xs text-gray-300 select-none">고급 설정</summary>
                    <div className="mt-2">
                        <label className="text-xs text-gray-300 block mb-1">Project</label>
                        <input
                            value={projectName}
                            onChange={(event) => onProjectNameChange(event.target.value)}
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
                        <p className="text-xs text-gray-400 mt-3 mb-2">Canopy Page</p>
                        <div className="flex gap-2">
                            <button
                                onClick={onPrevPage}
                                disabled={!canGoPrevPage}
                                className="flex-1 px-2 py-1.5 text-xs rounded-md border border-[#334155] bg-[#1f2937] hover:bg-[#273449] disabled:opacity-40 disabled:cursor-not-allowed"
                            >
                                이전
                            </button>
                            <button
                                onClick={onNextPage}
                                disabled={!canGoNextPage}
                                className="flex-1 px-2 py-1.5 text-xs rounded-md border border-[#334155] bg-[#1f2937] hover:bg-[#273449] disabled:opacity-40 disabled:cursor-not-allowed"
                            >
                                다음
                            </button>
                        </div>
                    </div>
                </details>

                <div className="rounded-lg border border-[#334155] bg-[#111827] p-3">
                    <p className="text-xs text-gray-400 mb-2">이 화면 사용법</p>
                    <ol className="text-[11px] text-gray-300 list-decimal list-inside space-y-1">
                        <li>진행상태 동기화로 현황 기준선 갱신</li>
                        <li>필터로 위험/막힘 구간 압축</li>
                        <li>필요 시 SonE 분석 입력만 펼쳐 재검증</li>
                    </ol>
                </div>
            </div>
        </div>
    );
}
