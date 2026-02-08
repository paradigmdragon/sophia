import { HearingTab } from "../components/HearingTab";

export function HearingPage() {
    return (
        <div className="h-full w-full flex flex-col bg-[#1e1e1e] text-gray-200 overflow-hidden">
            {/* Simple Header */}
            {/* Simple Header - Removed to fix alignment/cleanliness as per user feedback implies layout issues */}
            
            <div className="flex-1 overflow-hidden">
                <HearingTab />
            </div>
        </div>
    );
}
