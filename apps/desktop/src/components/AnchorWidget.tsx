import { useState, useEffect } from "react";
import { AnchorMenu } from "./AnchorMenu";
import { inboxService } from "../lib/inboxService";
import { useNavigate } from "react-router-dom";

export function AnchorWidget() {
    const navigate = useNavigate();
    const [isOpen, setIsOpen] = useState(false);
    const [itemCount, setItemCount] = useState(0);
    const [isPulsing, setIsPulsing] = useState(false);

    useEffect(() => {
        checkInbox();
        const interval = setInterval(checkInbox, 5000);
        return () => clearInterval(interval);
    }, []);

    const checkInbox = async () => {
        const items = await inboxService.getPendingItems();
        setItemCount(items.length);
        if (items.length > 0) {
            setIsPulsing(true);
        } else {
            setIsPulsing(false);
        }
    };

    const toggleMenu = () => setIsOpen(!isOpen);

    const handleNavigate = (view: 'journal' | 'chat') => {
        if (view === 'journal') navigate('/note');
        if (view === 'chat') navigate('/chat');
        setIsOpen(false);
    };

    return (
        <div className="fixed bottom-6 right-6 flex flex-col items-end z-50">
            
            {/* Menu Popover */}
            <AnchorMenu 
                isOpen={isOpen} 
                onClose={() => setIsOpen(false)}
                onNavigate={handleNavigate}
                unreadCount={itemCount}
            />

            {/* Anchor Button */}
            <button 
                onClick={toggleMenu}
                className={`
                    w-12 h-12 rounded-full shadow-2xl flex items-center justify-center transition-all duration-300 relative
                    ${isOpen 
                        ? 'bg-blue-600 scale-110' 
                        : 'bg-[#252526] hover:bg-[#333] border border-[#444]'
                    }
                `}
                title="Sophia Anchor"
            >
                {/* Simple Dot Icon */}
                <div className={`w-3 h-3 rounded-full transition-colors duration-300 ${isOpen || itemCount > 0 ? 'bg-white' : 'bg-gray-500'}`} />
                
                {/* Pulse Animation for Has Thoughts */}
                {!isOpen && isPulsing && (
                    <span className="absolute inset-0 rounded-full animate-ping bg-blue-500 opacity-20"></span>
                )}
                
                {/* Red Badge */}
                {!isOpen && itemCount > 0 && (
                    <span className="absolute -top-1 -right-1 flex h-4 w-4">
                        <span className="relative inline-flex rounded-full h-4 w-4 bg-red-500 text-[9px] text-white items-center justify-center font-bold shadow-sm">
                            {itemCount}
                        </span>
                    </span>
                )}
            </button>
        </div>
    );
}
