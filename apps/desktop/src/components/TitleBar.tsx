import { useNavigate, useLocation } from "react-router-dom";
import { Settings, Edit2, Film, LayoutDashboard } from "lucide-react";

export function TitleBar() {
    const navigate = useNavigate();
    const location = useLocation();

    const isActive = (path: string) => {
        if (path === '/' && (location.pathname === '/' || location.pathname === '/note')) return true;
        if (path === '/hearing' && location.pathname === '/hearing') return true;
        return false;
    };

    return (
        <header 
            data-tauri-drag-region 
            className="flex items-center justify-between h-10 px-3 bg-[#1e1e1e] border-b border-[#333] select-none relative z-[100] flex-shrink-0"
            style={{ WebkitAppRegion: "drag" } as any}
        >
            {/* Left: Drag Region + Title */}
            <div 
                className="flex items-center flex-1 h-full pl-20" 
                data-tauri-drag-region
            >
                <span 
                    data-tauri-drag-region 
                    className="font-bold text-gray-400 text-sm tracking-wide cursor-default"
                >
                    Sophia
                </span>
            </div>

            {/* Right: Buttons (No Drag) */}
            <div 
                className="flex items-center gap-1"
                style={{ WebkitAppRegion: "no-drag" } as any}
            >
                 <button 
                    onClick={() => navigate('/')}
                    className={`p-1.5 rounded-md transition-colors ${isActive('/') ? 'text-blue-400 bg-[#252526]' : 'text-gray-400 hover:text-white hover:bg-[#333]'}`}
                    title="Editor"
                 >
                    <Edit2 size={16} />
                 </button>

                 <button 
                    onClick={() => navigate('/hearing')}
                    className={`p-1.5 rounded-md transition-colors ${isActive('/hearing') ? 'text-purple-400 bg-[#252526]' : 'text-gray-400 hover:text-white hover:bg-[#333]'}`}
                    title="Hearing / Captions"
                 >
                    <Film size={16} />
                 </button>

                 <button 
                    onClick={() => navigate('/settings')}
                    className={`p-1.5 rounded-md transition-colors ${isActive('/settings') ? 'text-green-400 bg-[#252526]' : 'text-gray-400 hover:text-white hover:bg-[#333]'}`}
                    title="Settings"
                 >
                    <Settings size={16} />
                 </button>

                 <div className="w-[1px] h-4 bg-[#333] mx-1"></div>

                 <button 
                    onClick={() => navigate('/report')}
                    className={`p-1.5 rounded-md transition-colors ${isActive('/report') ? 'text-green-500 bg-[#252526]' : 'text-gray-400 hover:text-green-500 hover:bg-[#333]'}`}
                    title="Sophia Forest"
                 >
                    <LayoutDashboard size={16} />
                 </button>
            </div>
        </header>
    );
}
