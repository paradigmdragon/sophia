// import React from 'react';

interface AnchorMenuProps {
    isOpen: boolean;
    onClose: () => void;
    onNavigate: (view: 'journal' | 'chat') => void;
    unreadCount: number;
}

export function AnchorMenu({ isOpen, onClose, onNavigate, unreadCount }: AnchorMenuProps) {
    if (!isOpen) return null;

    return (
        <div className="absolute bottom-16 right-0 w-48 bg-[#1e1e1e] border border-[#333] shadow-xl rounded-lg overflow-hidden flex flex-col z-50 animate-fade-in-up">
            {/* Header */}
            <div className="px-4 py-3 border-b border-[#333] bg-[#252526]">
                <span className="text-xs font-bold text-gray-300">안녕하세요 주인님!</span>
            </div>

            {/* Menu Items */}
            <div className="py-1">
                <button 
                    onClick={() => { onNavigate('journal'); onClose(); }}
                    className="w-full text-left px-4 py-2 text-sm text-gray-300 hover:bg-[#2d2d2d] hover:text-white transition-colors flex items-center"
                >
                    <span className="mr-2">📝</span>
                    소피아 노트
                </button>
                
                <button 
                    onClick={() => { onNavigate('chat'); onClose(); }}
                    className="w-full text-left px-4 py-2 text-sm text-gray-300 hover:bg-[#2d2d2d] hover:text-white transition-colors flex items-center justify-between"
                >
                    <div className="flex items-center">
                        <span className="mr-2">💬</span>
                        대화하기
                    </div>
                    {unreadCount > 0 && (
                        <span className="bg-red-500 text-white text-[10px] font-bold px-1.5 py-0.5 rounded-full">
                            {unreadCount}
                        </span>
                    )}
                </button>
            </div>
        </div>
    );
}
