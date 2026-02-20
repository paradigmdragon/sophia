import { Routes, Route, useLocation } from "react-router-dom";
import { EditorPage } from "./pages/EditorPage";
import { SophiaNotePage } from "./pages/SophiaNotePage";
import { ChatPage } from "./pages/ChatPage";
import { HearingPage } from "./pages/HearingPage";
import { SettingsPage } from "./pages/SettingsPage";
import { AnchorWidget } from "./components/AnchorWidget";
import { TitleBar } from "./components/TitleBar";
import { ReportPage } from "./pages/ReportPage";

function App() {
  const location = useLocation();

  // Hide Anchor on Chat and Settings pages
  const showAnchor = location.pathname !== '/chat' && location.pathname !== '/settings';

  return (
    <div className="flex flex-col h-screen bg-[#1e1e1e] text-white overflow-hidden relative">
      {/* Custom Title Bar Navigation */}
      <TitleBar />

      <div className="flex-1 overflow-hidden relative z-0">
        <Routes>
          <Route path="/" element={<EditorPage />} />
          <Route path="/hearing" element={<HearingPage />} />
          <Route path="/note" element={<SophiaNotePage />} />
          <Route path="/chat" element={<ChatPage />} />
          <Route path="/settings" element={<SettingsPage />} />
          <Route path="/report" element={<ReportPage />} />
        </Routes>
      </div>

      {/* Global Anchor Widget (Hidden on Chat/Settings) */}
      {showAnchor && <AnchorWidget />}
    </div>
  );
}

export default App;
