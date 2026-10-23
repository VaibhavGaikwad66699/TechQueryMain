import React, { useState, useEffect, useCallback, useRef } from 'react';
import { Navbar } from './components/Navbar';
import { Sidebar } from './components/Sidebar';
import { ChatInterface } from './components/ChatInterface';
import { DocumentManager } from './components/DocumentManager';
import { PreferencesModal } from './components/PreferencesModal';
import { AuthModal } from './components/AuthModal';
import { api } from './services/api';
import { useAuth } from './context/AuthContext';
import { Conversation } from './types';
import { HealthSnapshot, healthForAccount } from './healthSnapshot';
import { LANGUAGE_FILTERS } from './scope';

export const App: React.FC = () => {
  const { user, preferences } = useAuth();
  const accountVersion = useRef(0);
  const appliedPreference = useRef('');
  const [currentTab, setCurrentTab] = useState<'chat' | 'documents' | 'preferences'>('chat');
  const [healthSnapshot, setHealthSnapshot] = useState<HealthSnapshot | null>(null);
  const systemHealth = healthForAccount(healthSnapshot, user?.id ?? null);
  const [subjects, setSubjects] = useState<string[]>(LANGUAGE_FILTERS);
  const [selectedSubject, setSelectedSubject] = useState<string>('All');

  // Conversation state
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeConversationId, setActiveConversationId] = useState<number | null>(null);
  const [newTopicVersion, setNewTopicVersion] = useState(0);

  // Modals & Drawers
  const [authModalOpen, setAuthModalOpen] = useState(false);
  const [preferencesModalOpen, setPreferencesModalOpen] = useState(false);
  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false);

  // Fetch initial health and subjects
  const fetchHealthAndSubjects = useCallback(async () => {
    const version = accountVersion.current;
    const accountId = user?.id ?? null;
    try {
      const health = await api.getHealth();
      const subs = await api.getSubjects();
      if (version !== accountVersion.current) return;
      setHealthSnapshot({ accountId, health });
      setSubjects(subs);
      setSelectedSubject(current => subs.includes(current) ? current : 'All');
    } catch (err) {
      console.error('Error checking system health:', err);
    }
  }, [user?.id]);

  useEffect(() => {
    accountVersion.current++;
    setSubjects(LANGUAGE_FILTERS);
    setSelectedSubject('All');
    fetchHealthAndSubjects();
    const interval = setInterval(fetchHealthAndSubjects, 30000);
    return () => clearInterval(interval);
  }, [user?.id, fetchHealthAndSubjects]);

  useEffect(() => {
    const preferenceKey = `${user?.id ?? 'guest'}:${preferences.preferred_subject}`;
    if (appliedPreference.current !== preferenceKey && subjects.includes(preferences.preferred_subject)) {
      setSelectedSubject(preferences.preferred_subject);
      appliedPreference.current = preferenceKey;
    }
  }, [user?.id, preferences.preferred_subject, subjects]);

  useEffect(() => {
    let canceled = false;
    setConversations([]);
    setActiveConversationId(null);
    if (user) {
      api.listConversations().then(list => {
        if (!canceled) {
          setConversations(list);
          setActiveConversationId(list[0]?.id ?? null);
        }
      }).catch(err => console.error('Error fetching conversations:', err));
    }
    return () => { canceled = true; };
  }, [user?.id]);

  const handleNewConversation = () => {
    setActiveConversationId(null);
    setNewTopicVersion(version => version + 1);
    setCurrentTab('chat');
  };

  const handleDeleteConversation = async (id: number) => {
    try {
      await api.deleteConversation(id);
      setConversations((prev) => prev.filter((c) => c.id !== id));
      if (activeConversationId === id) {
        setActiveConversationId(null);
      }
    } catch (err: any) {
      alert(`Could not delete conversation: ${err.message}`);
    }
  };

  const handleConversationCreated = (conv: Conversation) => {
    setConversations((prev) => [conv, ...prev]);
    setActiveConversationId(conv.id);
  };

  return (
    <div className="h-dvh overflow-hidden bg-slate-950 flex flex-col text-slate-100">
      {/* Top Navigation */}
      <Navbar
        currentTab={currentTab}
        setCurrentTab={(tab) => {
          if (tab === 'preferences') {
            setPreferencesModalOpen(true);
          } else {
            setCurrentTab(tab);
          }
        }}
        systemHealth={systemHealth}
        onOpenAuth={() => setAuthModalOpen(true)}
        selectedSubject={selectedSubject}
        setSelectedSubject={setSelectedSubject}
        subjects={subjects}
      />

      {/* Main Workspace */}
      <div className="flex-1 min-h-0 min-w-0 flex overflow-hidden">
        {currentTab === 'chat' && (
          <>
            <Sidebar
              conversations={conversations}
              activeConversationId={activeConversationId}
              onSelectConversation={(id) => setActiveConversationId(id)}
              onNewConversation={handleNewConversation}
              onDeleteConversation={handleDeleteConversation}
              onOpenDocuments={() => setCurrentTab('documents')}
              onOpenPreferences={() => setPreferencesModalOpen(true)}
              isOpen={mobileSidebarOpen}
              onCloseMobile={() => setMobileSidebarOpen(false)}
            />
            <ChatInterface
              key={`${user?.id ?? 'guest'}:${newTopicVersion}`}
              activeConversationId={activeConversationId}
              onConversationCreated={handleConversationCreated}
              selectedSubject={selectedSubject}
              onSelectSubject={setSelectedSubject}
              onOpenMobileSidebar={() => setMobileSidebarOpen(true)}
              onOpenPreferences={() => setPreferencesModalOpen(true)}
            />
          </>
        )}

        {currentTab === 'documents' && (
          <DocumentManager
            key={user?.id ?? 'guest'}
            subjects={subjects}
            onDocumentCountChange={fetchHealthAndSubjects}
            onSubjectDeleted={name => {
              setSubjects(previous => previous.filter(subject => subject !== name));
              setSelectedSubject(current => current === name ? 'All' : current);
            }}
          />
        )}
      </div>

      {/* Preferences Modal */}
      <PreferencesModal
        isOpen={preferencesModalOpen}
        onClose={() => setPreferencesModalOpen(false)}
        subjects={subjects}
      />

      {/* Authentication Modal */}
      <AuthModal
        isOpen={authModalOpen}
        onClose={() => setAuthModalOpen(false)}
      />
    </div>
  );
};
