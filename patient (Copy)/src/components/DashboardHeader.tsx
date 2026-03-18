import { LogOut, MessageSquare } from 'lucide-react';

interface DashboardHeaderProps {
  onLogout: () => void;
  onOpenChatbox: () => void;
}

export function DashboardHeader({ onLogout, onOpenChatbox }: DashboardHeaderProps) {
  return (
    <header className="bg-[#581B98] text-white shadow-lg">
      <div className="max-w-7xl mx-auto px-4 py-4 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">REMONI</h1>
          <p className="text-purple-200 text-sm">Patient's Health Dashboard</p>
        </div>
        
        <div className="flex items-center gap-3">
          <button
            onClick={onOpenChatbox}
            className="flex items-center gap-2 bg-white/10 hover:bg-white/20 px-4 py-2 rounded-lg transition-colors"
          >
            <MessageSquare className="w-4 h-4" />
            <span>Chatbox</span>
          </button>
          <button
            onClick={onLogout}
            className="flex items-center gap-2 bg-white/10 hover:bg-white/20 px-4 py-2 rounded-lg transition-colors"
          >
            <LogOut className="w-4 h-4" />
            <span>Logout</span>
          </button>
        </div>
      </div>
    </header>
  );
}