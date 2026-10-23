import React from 'react';
import { Plus, MessageSquare, Trash2, BookOpen, Sliders, X } from 'lucide-react';
import { Conversation } from '../types';

interface SidebarProps {
  conversations: Conversation[];
  activeConversationId: number | null;
  onSelectConversation: (id: number) => void;
  onNewConversation: () => void;
  onDeleteConversation: (id: number) => void;
  onOpenDocuments: () => void;
  onOpenPreferences: () => void;
  isOpen: boolean;
  onCloseMobile: () => void;
}

export const Sidebar: React.FC<SidebarProps> = ({
  conversations,
  activeConversationId,
  onSelectConversation,
  onNewConversation,
  onDeleteConversation,
  onOpenDocuments,
  onOpenPreferences,
  isOpen,
  onCloseMobile,
}) => {
  return (
    <>
      {/* Mobile overlay */}
      {isOpen && (
        <div
          className="fixed inset-0 bg-black/60 z-30 md:hidden"
          onClick={onCloseMobile}
        />
      )}

      <aside
        className={`fixed md:static flex-shrink-0 inset-y-0 left-0 z-40 w-64 bg-slate-900 border-r border-slate-800 flex-col select-none ${
          isOpen ? 'flex' : 'hidden md:flex'
        }`}
      >
        <button aria-label="Close menu" onClick={onCloseMobile} className="md:hidden self-end p-3 text-slate-300"><X className="w-5 h-5" /></button>
        {/* Top Action: New Conversation */}
        <div className="p-3.5 border-b border-slate-800">
          <button
            onClick={() => {
              onNewConversation();
              onCloseMobile();
            }}
            className="w-full flex items-center justify-center space-x-2 bg-brand-600 hover:bg-brand-500 text-white font-semibold text-xs py-2.5 px-3 rounded-lg shadow-md shadow-brand-600/20 transition-all active:scale-95"
          >
            <Plus className="w-4 h-4" />
            <span>Start a new topic</span>
          </button>
        </div>

        {/* Conversations List */}
        <div className="flex-1 overflow-y-auto p-2 space-y-1">
          <div className="px-2 py-1 text-[11px] font-semibold text-slate-400 uppercase tracking-wider flex items-center justify-between">
            <span>Recent Sessions</span>
            <span className="text-[10px] bg-slate-800 px-1.5 py-0.5 rounded text-slate-400">
              {conversations.length}
            </span>
          </div>

          {conversations.length === 0 ? (
            <div className="p-4 text-center text-slate-400 text-xs">
              <MessageSquare className="w-6 h-6 mx-auto mb-2 opacity-40" />
              <p>No conversations yet.</p>
              <p className="text-[11px] mt-1 text-slate-400">Ask a technical question to begin!</p>
            </div>
          ) : (
            conversations.map((c) => {
              const isActive = c.id === activeConversationId;
              return (
                <div
                  role="button"
                  tabIndex={0}
                  onKeyDown={event => {
                    if (event.target !== event.currentTarget) return;
                    if (event.key === 'Enter' || event.key === ' ') {
                      event.preventDefault();
                      onSelectConversation(c.id);
                      onCloseMobile();
                    }
                  }}
                  key={c.id}
                  className={`group flex items-center justify-between px-3 py-2 rounded-lg text-xs cursor-pointer transition-colors ${
                    isActive
                      ? 'bg-slate-800 text-brand-300 font-medium border border-slate-700/60'
                      : 'text-slate-400 hover:bg-slate-800/50 hover:text-slate-200'
                  }`}
                  onClick={() => {
                    onSelectConversation(c.id);
                    onCloseMobile();
                  }}
                >
                  <div className="flex items-center space-x-2.5 truncate flex-1 min-w-0 pr-1">
                    <MessageSquare className={`w-3.5 h-3.5 flex-shrink-0 ${isActive ? 'text-brand-400' : 'text-slate-500'}`} />
                    <span className="truncate">{c.title}</span>
                  </div>

                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      if (confirm('Delete this conversation?')) {
                        onDeleteConversation(c.id);
                      }
                    }}
                    title="Delete Conversation"
                    aria-label={`Delete conversation: ${c.title}`}
                    className="md:opacity-0 group-hover:opacity-100 group-focus-within:opacity-100 p-2 hover:text-rose-400 transition-opacity rounded focus:outline-none focus-visible:ring-2 focus-visible:ring-rose-500/50"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                </div>
              );
            })
          )}
        </div>

        {/* Bottom Quick Tools */}
        <div className="p-3 border-t border-slate-800 bg-slate-950/40 space-y-1">
          <button
            onClick={() => {
              onOpenDocuments();
              onCloseMobile();
            }}
            className="w-full flex items-center space-x-2 text-slate-400 hover:text-slate-200 hover:bg-slate-800/60 text-xs px-2.5 py-2 rounded-lg transition-colors"
          >
            <BookOpen className="w-4 h-4 text-brand-400" />
            <span>Manage Textbooks</span>
          </button>

          <button
            onClick={() => {
              onOpenPreferences();
              onCloseMobile();
            }}
            className="w-full flex items-center space-x-2 text-slate-400 hover:text-slate-200 hover:bg-slate-800/60 text-xs px-2.5 py-2 rounded-lg transition-colors"
          >
            <Sliders className="w-4 h-4 text-brand-400" />
            <span>Learning preferences</span>
          </button>
        </div>
      </aside>
    </>
  );
};
