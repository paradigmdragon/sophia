import { useState, useEffect } from "react";
import { AnchorMenu } from "./AnchorMenu";
import { inboxService } from "../lib/inboxService";
import SonaEyeGraph from "./SonaEyeGraph";
import { useEpidoraState } from "../hooks/useEpidoraState";

export function AnchorWidget() {
    const [isOpen, setIsOpen] = useState(false);
    const [itemCount, setItemCount] = useState(0);
    const eyeMode = useEpidoraState();

    useEffect(() => {
        checkInbox();
        const interval = setInterval(checkInbox, 5000);
        return () => clearInterval(interval);
    }, []);

    const checkInbox = async () => {
        const items = await inboxService.getPendingItems();
        setItemCount(items.length);
    };

    const toggleMenu = () => setIsOpen(!isOpen);



    return (
        <div className="fixed bottom-6 right-6 flex flex-col items-end z-50">
            
            {/* Menu Popover */}
            <AnchorMenu 
                isOpen={isOpen} 
                onClose={() => setIsOpen(false)}
                // We'll pass the unread count here if needed, but for now just open/close
            />

            {/* Anchor Button */}
            <button 
                onClick={toggleMenu}
                className={`
                    w-14 h-14 rounded-full shadow-2xl flex items-center justify-center transition-all duration-300 relative overflow-hidden
                    ${isOpen 
                        ? 'bg-[#1e1e1e] ring-2 ring-blue-500/50' 
                        : 'bg-[#1e1e1e] hover:bg-[#252526] border border-[#333]'
                    }
                `}
                title="Sophia Anchor"
            >
                {/* Sona Eye Graph Logo */}
                <div className="w-full h-full flex items-center justify-center scale-[1.8]">
                    <SonaEyeGraph mode={eyeMode} />
                </div>
                
                {/* Red Badge */}
                {!isOpen && itemCount > 0 && (
                    <span className="absolute top-0 right-0 flex h-5 w-5 z-10">
                        <span className="relative inline-flex rounded-full h-5 w-5 bg-red-500 text-[10px] text-white items-center justify-center font-bold shadow-sm border border-[#1e1e1e]">
                            {itemCount}
                        </span>
                    </span>
                )}
            </button>
        </div>
    );
}
