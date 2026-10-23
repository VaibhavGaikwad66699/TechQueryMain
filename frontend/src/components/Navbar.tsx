import React from 'react';
import { BookOpen, Book, Sliders, LogIn, LogOut, AlertCircle, CheckCircle } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { SystemHealth } from '../types';
import { languageLabel } from '../scope';

interface NavbarProps {
  currentTab: 'chat' | 'documents' | 'preferences';
  setCurrentTab: (tab: 'chat' | 'documents' | 'preferences') => void;
  systemHealth: SystemHealth | null;
  onOpenAuth: () => void;
  selectedSubject: string;
  setSelectedSubject: (sub: string) => void;
  subjects: string[];
}

export const Navbar: React.FC<NavbarProps> = ({
  currentTab,
  setCurrentTab,
  systemHealth,
  onOpenAuth,
  selectedSubject,
  setSelectedSubject,
  subjects,
}) => {
  const { user, logout } = useAuth();

  const isGeminiConfigured = Boolean(systemHealth?.gemini?.configured);
  const docsCount = systemHealth?.database?.total_documents ?? 0;
  const textChunksCount = systemHealth?.database?.total_indexed_chunks ?? 0;
  const embeddedChunksCount = systemHealth?.database?.total_embedded_chunks ?? 0;

  return (
    <>
    <header className="h-16 flex-shrink-0 gap-2 border-b border-slate-800 bg-slate-900/90 backdrop-blur-md px-3 sm:px-4 flex items-center justify-between sticky top-0 z-30 select-none">
      {/* Left: Brand */}
      <div className="min-w-0 flex items-center gap-3 xl:gap-6">
        <button
          aria-label="TechQuery home"
          className="flex min-w-0 items-center gap-2 text-left"
          onClick={() => setCurrentTab('chat')}
        >
          <div className="w-9 h-9 flex-shrink-0 rounded-xl bg-brand-600 flex items-center justify-center shadow-lg shadow-brand-500/20">
            <BookOpen className="w-5 h-5 text-white" />
          </div>
          <div>
            <div className="flex items-center space-x-1.5">
              <span className="font-extrabold text-base tracking-tight text-slate-100">TechQuery</span>
              <span className="hidden xl:inline text-[10px] font-semibold bg-brand-500/20 text-brand-700 border border-brand-500/30 px-1.5 py-0.2 rounded-full">
                Study library
              </span>
            </div>
            <p className="hidden sm:block whitespace-nowrap text-[10px] text-slate-400">Default books + your subjects</p>
          </div>
        </button>

        {/* Navigation Tabs */}
        <nav className="hidden lg:flex items-center space-x-1">
          <button
            onClick={() => setCurrentTab('chat')}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
              currentTab === 'chat'
                ? 'bg-slate-800 text-brand-400 font-semibold shadow-sm'
                : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
            }`}
          >
            Chat &amp; QA
          </button>
          <button
            onClick={() => setCurrentTab('documents')}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium flex items-center space-x-1.5 transition-all ${
              currentTab === 'documents'
                ? 'bg-slate-800 text-brand-400 font-semibold shadow-sm'
                : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
            }`}
          >
            <Book className="w-3.5 h-3.5" />
            <span>Knowledge Base</span>
            <span
              title={systemHealth ? `Library status: ${embeddedChunksCount.toLocaleString()} embedded vectors / ${textChunksCount.toLocaleString()} text chunks across ${docsCount} books` : 'Checking your library'}
              className="bg-slate-700/80 text-slate-300 text-[10px] px-1.5 py-0.2 rounded-full font-mono"
            >
              {systemHealth ? docsCount : '…'}
            </span>
          </button>
          <button
            onClick={() => setCurrentTab('preferences')}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium flex items-center space-x-1.5 transition-all ${
              currentTab === 'preferences'
                ? 'bg-slate-800 text-brand-400 font-semibold shadow-sm'
                : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
            }`}
          >
            <Sliders className="w-3.5 h-3.5" />
            <span>Preferences</span>
          </button>
        </nav>
      </div>

      {/* Center: Subject Filter & Status */}
      <div className="hidden xl:flex items-center space-x-4">
        {/* Subject dropdown */}
        <div className="flex items-center space-x-1.5 bg-slate-950/70 border border-slate-800 rounded-lg px-2.5 py-1 text-xs">
          <span className="text-slate-500 font-medium text-[11px]">Subject:</span>
          <select
            aria-label="Filter questions by subject"
            value={selectedSubject}
            onChange={(e) => setSelectedSubject(e.target.value)}
            className="max-w-40 bg-transparent text-slate-200 font-medium focus:outline-none cursor-pointer text-xs"
          >
            {subjects.map((sub) => (
              <option key={sub} value={sub} className="bg-slate-900 text-slate-200">
                {languageLabel(sub)}
              </option>
            ))}
          </select>
        </div>

        {/* Study service status */}
        <div
          className={`flex items-center space-x-1.5 px-2.5 py-1 rounded-full text-[11px] border ${
            !systemHealth ? 'bg-slate-800 text-slate-400 border-slate-700' : isGeminiConfigured
              ? 'bg-emerald-500/10 text-emerald-600 border-emerald-500/30'
              : 'bg-amber-500/10 text-amber-600 border-amber-500/30 cursor-pointer'
          }`}
          title={
            !systemHealth ? 'Checking the study service' : isGeminiConfigured
              ? `Model configured (${systemHealth?.gemini?.model || 'Gemini'}); live provider availability is unverified`
              : 'Local study mode is active. Configure GEMINI_API_KEY in backend/.env for AI explanations.'
          }
          onClick={() => {
            if (systemHealth && !isGeminiConfigured) {
              alert(
                'Local study mode is active. Upload PDFs to search their passages, or connect an answer service in project settings for generated explanations.'
              );
            }
          }}
        >
          {!systemHealth ? <span>Checking service…</span> : isGeminiConfigured ? (
            <>
              <CheckCircle className="w-3 h-3 text-emerald-600" />
              <span>Answer service configured</span>
            </>
          ) : (
            <>
              <AlertCircle className="w-3 h-3 text-amber-600" />
              <span>Local study mode</span>
            </>
          )}
        </div>
      </div>

      {/* Right: Auth / Profile */}
      <div className="flex flex-shrink-0 items-center space-x-3">
        {user ? (
          <div className="flex items-center space-x-3">
            <div className="flex items-center space-x-2 bg-slate-800/80 px-2.5 py-1 rounded-lg border border-slate-700/60">
              <div className="w-6 h-6 rounded-full bg-brand-500/20 text-brand-400 flex items-center justify-center font-bold text-xs">
                {user.username.charAt(0).toUpperCase()}
              </div>
              <div className="text-left hidden lg:block">
                <p className="max-w-24 truncate text-xs font-semibold text-slate-200 leading-none">{user.username}</p>
                <p className="text-[10px] text-slate-400 capitalize">{user.role}</p>
              </div>
            </div>
            <button
              onClick={logout}
              title="Logout"
              className="p-1.5 text-slate-400 hover:text-rose-400 hover:bg-slate-800 rounded-lg transition-colors"
            >
              <LogOut className="w-4 h-4" />
            </button>
          </div>
        ) : (
          <button
            onClick={onOpenAuth}
            className="flex items-center space-x-1.5 bg-brand-600 hover:bg-brand-500 text-white text-xs font-semibold px-3.5 py-2 rounded-lg shadow-md shadow-brand-500/20 transition-all active:scale-95"
          >
            <LogIn className="w-3.5 h-3.5" />
            <span>Sign In / Register</span>
          </button>
        )}
      </div>
    </header>
    <div className="xl:hidden flex flex-shrink-0 items-center gap-2 px-3 py-2 border-b border-slate-800 bg-slate-900">
      <nav aria-label="Mobile navigation" className="lg:hidden flex flex-shrink-0 items-center gap-1">
        <button onClick={() => setCurrentTab('chat')} className={`px-2 py-2 rounded-lg text-xs ${currentTab === 'chat' ? 'bg-slate-800 text-brand-700' : 'text-slate-300'}`}>Chat</button>
        <button onClick={() => setCurrentTab('documents')} className={`px-2 py-2 rounded-lg text-xs ${currentTab === 'documents' ? 'bg-slate-800 text-brand-700' : 'text-slate-300'}`}>Library</button>
        <button aria-label="Learning preferences" onClick={() => setCurrentTab('preferences')} className="p-2 text-brand-700"><Sliders className="w-4 h-4" /></button>
      </nav>
      <select aria-label="Filter questions by subject" value={selectedSubject} onChange={event => setSelectedSubject(event.target.value)} className="min-w-0 flex-1 max-w-xs bg-slate-950 border border-slate-800 rounded-lg px-2 py-2 text-xs text-slate-200">
        {subjects.map(subject => <option key={subject} value={subject}>{languageLabel(subject)}</option>)}
      </select>
    </div>
    </>
  );
};
