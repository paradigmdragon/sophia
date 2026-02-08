import { Routes, Route, Navigate } from "react-router-dom";
import { NotePage } from "./pages/NotePage";
import { ChatPage } from "./pages/ChatPage";
import { AnchorWidget } from "./components/AnchorWidget";
import { SettingsModal, LineWrapSettings, DEFAULT_SETTINGS } from "./components/SettingsModal";
import { useState } from "react";

function App() {
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [lineWrapSettings, setLineWrapSettings] = useState<LineWrapSettings>(DEFAULT_SETTINGS);

  const handleSaveSettings = (newSettings: LineWrapSettings) => {
      setLineWrapSettings(newSettings);
      localStorage.setItem("sophia_settings_v1", JSON.stringify({ line_wrap: newSettings }));
  };

  return (
    <div className="flex flex-col h-screen bg-[#1e1e1e] text-white overflow-hidden relative">
      <div className="flex-1 overflow-hidden relative">
        <Routes>
          <Route path="/" element={<Navigate to="/note" replace />} />
          <Route path="/note" element={<NotePage />} />
          <Route path="/chat" element={<ChatPage />} />
        </Routes>
      </div>

      {/* Global Anchor Widget */}
      <AnchorWidget />

      <SettingsModal 
        isOpen={isSettingsOpen} 
        onClose={() => setIsSettingsOpen(false)}
        settings={lineWrapSettings}
        onSave={handleSaveSettings}
      />
    </div>
  );
}

export default App;
