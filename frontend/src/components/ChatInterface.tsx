import React, { useState, useEffect, useRef } from 'react';
import { Send, User as UserIcon, BookOpen, Sliders, AlertCircle, Copy, Check, Menu } from 'lucide-react';
import { api } from '../services/api';
import { useAuth } from '../context/AuthContext';
import { SourceCard } from './SourceCard';
import { Conversation, Message } from '../types';

interface ChatInterfaceProps {
  activeConversationId: number | null;
  onConversationCreated: (conv: Conversation) => void;
  selectedSubject: string;
  onSelectSubject: (subject: string) => void;
  onOpenMobileSidebar: () => void;
  onOpenPreferences: () => void;
}

const MAX_QUESTION_CHARACTERS = 4000;

const getResponseModeDetails = (
  mode?: string | null,
  abstained?: boolean | null
): { label: string; badgeClass: string } => {
  if (abstained || mode === 'abstained') {
    return {
      label: 'Insufficient evidence',
      badgeClass: 'bg-amber-500/10 text-amber-500 border-amber-500/30 font-semibold',
    };
  }
  if (mode === 'generated') {
    return {
      label: 'Generated answer',
      badgeClass: 'bg-brand-500/10 text-brand-500 border-brand-500/30 font-semibold',
    };
  }
  if (mode === 'source_excerpts') {
    return {
      label: 'PDF excerpts',
      badgeClass: 'bg-slate-800 text-slate-300 border-slate-700/60 font-semibold',
    };
  }
  return {
    label: 'Study answer',
    badgeClass: 'bg-slate-800 text-slate-400 border-slate-700/60 font-medium',
  };
};

const getRetrievalLabel = (mode?: string | null): string | null => {
  if (!mode || mode === 'none') return null;
  switch (mode.toLowerCase()) {
    case 'semantic':
      return 'Semantic search';
    case 'lexical':
      return 'Keyword search';
    case 'hybrid':
      return 'Combined search';
    default:
      return `${mode} search`;
  }
};

export const ChatInterface: React.FC<ChatInterfaceProps> = ({
  activeConversationId,
  onConversationCreated,
  selectedSubject,
  onSelectSubject,
  onOpenMobileSidebar,
  onOpenPreferences,
}) => {
  const { preferences, user } = useAuth();
  const [messages, setMessages] = useState<Message[]>([]);
  const [inputQuery, setInputQuery] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [copiedId, setCopiedId] = useState<number | null>(null);

  // Quick prompt toggles
  const [currentLevel, setCurrentLevel] = useState(preferences.explanation_level);
  const [currentStyle, setCurrentStyle] = useState(preferences.answer_style);
  const [currentExamples, setCurrentExamples] = useState(preferences.include_examples);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const contextVersion = useRef(0);
  const sendController = useRef<AbortController | null>(null);
  const createdConversation = useRef<number | null>(null);

  // Sync with context preferences when context changes
  useEffect(() => {
    setCurrentLevel(preferences.explanation_level);
    setCurrentStyle(preferences.answer_style);
    setCurrentExamples(preferences.include_examples);
  }, [preferences]);

  // Load messages when activeConversationId changes
  useEffect(() => {
    // Publishing a just-created conversation must not race its first answer
    // against an empty history load, or cancel its own request.
    if (activeConversationId && createdConversation.current === activeConversationId) {
      createdConversation.current = null;
      return;
    }
    const version = ++contextVersion.current;
    sendController.current?.abort();
    const controller = new AbortController();
    setMessages([]);
    setError(null);
    setLoading(Boolean(activeConversationId));
    if (activeConversationId) {
      api.getConversation(activeConversationId, controller.signal).then(conv => {
        if (contextVersion.current === version && !controller.signal.aborted) setMessages(conv.messages || []);
      }).catch(err => {
        if (!controller.signal.aborted && contextVersion.current === version) setError(err.message || 'Could not load conversation history.');
      }).finally(() => {
        if (!controller.signal.aborted && contextVersion.current === version) setLoading(false);
      });
    }
    return () => controller.abort();
  }, [activeConversationId]);

  useEffect(() => () => {
    contextVersion.current++;
    sendController.current?.abort();
  }, []);

  // Scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, loading]);

  const handleSend = async (customPrompt?: string, subjectOverride?: string) => {
    const questionText = (customPrompt || inputQuery).trim();
    const questionSubject = subjectOverride || selectedSubject;
    if (!questionText || loading) return;

    if (questionText.length > MAX_QUESTION_CHARACTERS) {
      setError(`Question cannot exceed ${MAX_QUESTION_CHARACTERS} characters (current length: ${questionText.length}).`);
      return;
    }

    setError(null);
    setLoading(true);
    const version = contextVersion.current;
    const controller = new AbortController();
    sendController.current = controller;

    // Optimistic user message
    const tempUserMsg: Message = {
      id: Date.now(),
      conversation_id: activeConversationId || 0,
      role: 'user',
      content: questionText,
      created_at: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, tempUserMsg]);

    try {
      let targetConvId = activeConversationId;

      // If no active conversation and user is logged in, create one first
      if (!targetConvId && user) {
        const newConv = await api.createConversation({
          title: questionText.slice(0, 35),
          subject: questionSubject,
        });
        if (contextVersion.current !== version || controller.signal.aborted) return;
        targetConvId = newConv.id;
        createdConversation.current = newConv.id;
        onConversationCreated(newConv);
      }

      let response;
      if (targetConvId) {
        // Logged-in conversation flow
        response = await api.sendMessage(targetConvId, {
          question: questionText,
          subject: questionSubject,
          explanation_level: currentLevel,
          answer_style: currentStyle,
          include_examples: currentExamples,
        }, controller.signal);
      } else {
        // Direct Query flow (e.g. guest mode)
        response = await api.directQuery({
          question: questionText,
          subject: questionSubject,
          explanation_level: currentLevel,
          answer_style: currentStyle,
          include_examples: currentExamples,
        }, controller.signal);
      }

      if (contextVersion.current !== version || controller.signal.aborted) return;

      const asstMsg: Message = {
        id: response.message_id || Date.now() + 1,
        conversation_id: targetConvId || 0,
        role: 'assistant',
        content: response.answer,
        sources: response.sources,
        suggested_questions: response.abstained ? [] : (response.suggested_questions || []),
        response_mode: response.response_mode,
        retrieval_mode: response.retrieval_mode,
        abstained: response.abstained,
        created_at: new Date().toISOString(),
      };

      setMessages((prev) => [...prev, asstMsg]);

      // Only clear input drafted text upon confirmed success
      if (!customPrompt) {
        setInputQuery('');
      }
    } catch (err: any) {
      if (contextVersion.current !== version || controller.signal.aborted) return;
      setError(err.message || 'Error communicating with TechQuery AI engine.');
      // Remove optimistic user message on failure so history is honest
      setMessages((prev) => prev.filter((m) => m.id !== tempUserMsg.id));
    } finally {
      if (contextVersion.current === version && !controller.signal.aborted) setLoading(false);
    }
  };

  const copyToClipboard = (text: string, id: number) => {
    navigator.clipboard.writeText(text);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 1500);
  };

  const sampleQuestions = [
    { text: 'How do pointers and arrays work in C?', subject: 'C' },
    { text: 'How do constructors and destructors work in C++?', subject: 'C++' },
    { text: 'Explain Java interfaces with a simple code example.', subject: 'Java' },
    { text: 'What is the difference between lists and tuples in Python?', subject: 'Python' },
  ];

  return (
    <div className="flex-1 min-w-0 min-h-0 flex flex-col bg-slate-950/60 overflow-hidden relative">
      {/* Top Mobile Bar */}
      <div className="md:hidden flex items-center justify-between p-3 border-b border-slate-800 bg-slate-900">
        <button
          onClick={onOpenMobileSidebar}
          className="p-1.5 rounded-lg bg-slate-800 text-slate-300"
          title="Open Menu"
        >
          <Menu className="w-4 h-4" />
        </button>
        <span className="text-xs font-bold text-slate-200">
          {selectedSubject === 'All' ? 'All my subjects' : selectedSubject}
        </span>
        <button
          onClick={onOpenPreferences}
          className="p-1.5 rounded-lg bg-slate-800 text-brand-400"
          title="Learning Preferences"
        >
          <Sliders className="w-4 h-4" />
        </button>
      </div>

      {/* Messages Scroll Area */}
      <div className="flex-1 overflow-y-auto p-4 md:p-6 space-y-6">
        {messages.length === 0 ? (
          <div className="max-w-2xl mx-auto my-auto text-center py-12 px-4 space-y-6">
            <div className="w-16 h-16 rounded-2xl bg-gradient-to-tr from-brand-600 to-indigo-600 flex items-center justify-center mx-auto shadow-xl shadow-brand-500/20">
              <BookOpen className="w-8 h-8 text-white" />
            </div>

            <div>
              <h2 className="text-xl md:text-2xl font-black text-slate-100 tracking-tight">
                Answers backed by your books
              </h2>
              <p className="text-xs text-slate-400 mt-2 leading-relaxed">
                Start with the included C, C++, Java, and Python books, or add a personal subject and reference PDF in Knowledge Base. Answers use your selected books and learning preferences, with sources you can check.
              </p>
            </div>

            {/* Quick Sample Prompts */}
            <div className="text-left space-y-2 pt-2">
              <p className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider text-center">
                Choose a subject to get started
              </p>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                {sampleQuestions.map((q, idx) => (
                  <button
                    key={idx}
                    onClick={() => { onSelectSubject(q.subject); handleSend(q.text, q.subject); }}
                    className="p-3 text-left rounded-xl bg-slate-900 border border-slate-800 hover:border-brand-500/50 hover:bg-slate-800 text-xs text-slate-300 hover:text-slate-100 transition-all group focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500/50"
                  >
                    <span className="text-[10px] text-brand-400 font-mono block mb-1">
                      {q.subject}
                    </span>
                    <span className="font-medium group-hover:text-brand-700">{q.text}</span>
                  </button>
                ))}
              </div>
            </div>
          </div>
        ) : (
          messages.map((msg) => {
            const modeInfo = getResponseModeDetails(msg.response_mode, msg.abstained);
            const retrievalLabel = getRetrievalLabel(msg.retrieval_mode);

            return (
              <div
                key={msg.id}
                className={`flex min-w-0 space-x-2 sm:space-x-3.5 max-w-4xl mx-auto ${
                  msg.role === 'user' ? 'justify-end' : 'justify-start'
                }`}
              >
                {msg.role === 'assistant' && (
                  <div className="w-8 h-8 rounded-xl bg-brand-600/20 border border-brand-500/30 flex items-center justify-center flex-shrink-0 text-brand-400 shadow-sm mt-1">
                    <BookOpen className="w-4 h-4" />
                  </div>
                )}

                <div
                  className={`min-w-0 break-words rounded-2xl p-3 sm:p-4 text-xs leading-relaxed max-w-2xl space-y-3 ${
                    msg.role === 'user'
                      ? 'bg-brand-600 text-white rounded-tr-none shadow-md shadow-brand-600/20'
                      : 'bg-slate-900 border border-slate-800 text-slate-200 rounded-tl-none shadow-lg'
                  }`}
                >
                  {/* Header for assistant message */}
                  {msg.role === 'assistant' && (
                    <div className="flex flex-wrap items-center justify-between pb-2 border-b border-slate-800 text-[11px] text-slate-400 gap-1.5">
                      <div className="flex flex-wrap items-center gap-1.5">
                        <span className={`px-2 py-0.5 rounded text-[10px] font-medium border ${modeInfo.badgeClass}`}>
                          {modeInfo.label}
                        </span>

                        {retrievalLabel && (
                          <span className="px-2 py-0.5 rounded text-[10px] font-medium bg-slate-800 text-slate-300 border border-slate-700/60">
                            {retrievalLabel}
                          </span>
                        )}

                        {msg.sources && msg.sources.length > 0 && (
                          <span className="bg-slate-800/80 text-slate-300 px-2 py-0.5 rounded text-[10px] border border-slate-700/60">
                            {msg.sources.length} {msg.sources.length === 1 ? 'Source passage' : 'Source passages'}
                          </span>
                        )}
                      </div>

                      <button
                        onClick={() => copyToClipboard(msg.content, msg.id)}
                        className="hover:text-slate-200 p-1 rounded transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500/50"
                        title="Copy Answer"
                        aria-label="Copy Answer"
                      >
                        {copiedId === msg.id ? (
                          <Check className="w-3.5 h-3.5 text-emerald-500" />
                        ) : (
                          <Copy className="w-3.5 h-3.5" />
                        )}
                      </button>
                    </div>
                  )}

                  {/* Content */}
                  <div className="prose prose-invert max-w-none text-xs whitespace-pre-wrap leading-relaxed">
                    {msg.content}
                  </div>

                  {/* Citations / Sources */}
                  {msg.sources && msg.sources.length > 0 && (
                    <div className="pt-3 border-t border-slate-800/80 space-y-2">
                      <p className="text-[10px] font-bold text-slate-400 uppercase tracking-wider flex items-center space-x-1">
                        <BookOpen className="w-3 h-3 text-brand-400" />
                        <span>Retrieved Textbook Sources:</span>
                      </p>
                      <div className="grid grid-cols-1 gap-1.5">
                        {msg.sources.map((source, sIdx) => (
                          <SourceCard key={sIdx} source={source} />
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Continue learning follow-ups (suppressed when abstained) */}
                  {msg.role === 'assistant' && !msg.abstained && msg.suggested_questions && msg.suggested_questions.length > 0 && (
                    <div className="pt-3 border-t border-slate-800/80">
                      <p className="text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-2">
                        Continue learning
                      </p>
                      <div className="flex flex-wrap gap-2">
                        {msg.suggested_questions.map((question) => (
                          <button
                            key={question}
                            onClick={() => handleSend(question)}
                            className="text-left text-[11px] px-2.5 py-1.5 rounded-lg bg-slate-800 hover:bg-brand-100 text-slate-200 hover:text-brand-700 border border-slate-700 transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500/50"
                          >
                            {question}
                          </button>
                        ))}
                      </div>
                    </div>
                  )}
                </div>

                {msg.role === 'user' && (
                  <div className="w-8 h-8 rounded-xl bg-slate-800 border border-slate-700 flex items-center justify-center flex-shrink-0 text-slate-300 mt-1">
                    <UserIcon className="w-4 h-4" />
                  </div>
                )}
              </div>
            );
          })
        )}

        {/* Loading Indicator */}
        {loading && (
          <div className="flex space-x-3.5 max-w-4xl mx-auto justify-start">
            <div className="w-8 h-8 rounded-xl bg-brand-600/20 border border-brand-500/30 flex items-center justify-center flex-shrink-0 text-brand-400 animate-pulse">
              <BookOpen className="w-4 h-4" />
            </div>
            <div className="bg-slate-900 border border-slate-800 rounded-2xl rounded-tl-none p-4 text-xs text-slate-400 flex items-center space-x-3 shadow-lg">
              <div className="flex space-x-1.5">
                <div className="w-2 h-2 rounded-full bg-brand-500 animate-bounce" />
                <div className="w-2 h-2 rounded-full bg-brand-500 animate-bounce [animation-delay:0.2s]" />
                <div className="w-2 h-2 rounded-full bg-brand-500 animate-bounce [animation-delay:0.4s]" />
              </div>
              <span>Looking through your study library...</span>
            </div>
          </div>
        )}

        {/* Error Message */}
        {error && (
          <div className="max-w-4xl mx-auto p-3.5 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-500 text-xs flex items-center space-x-2">
            <AlertCircle className="w-4 h-4 flex-shrink-0" />
            <span>{error}</span>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Bottom Query Input Box */}
      <div className="p-4 border-t border-slate-800 bg-slate-900/90 backdrop-blur-md select-none">
        <div className="max-w-4xl mx-auto space-y-2">
          {/* Quick-toggles bar */}
          <div className="flex flex-wrap items-center justify-between text-[11px] gap-2">
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-slate-500">Tuning:</span>

              {/* Level cycle */}
              <button
                type="button"
                onClick={() => {
                  const next =
                    currentLevel === 'Beginner'
                      ? 'Intermediate'
                      : currentLevel === 'Intermediate'
                      ? 'Advanced'
                      : 'Beginner';
                  setCurrentLevel(next);
                }}
                className="bg-slate-800 hover:bg-slate-700 text-brand-300 px-2 py-0.5 rounded border border-slate-700/80 font-mono transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500/50"
                title="Click to change explanation level"
              >
                Level: {currentLevel}
              </button>

              {/* Style cycle */}
              <button
                type="button"
                onClick={() => {
                  const next = currentStyle === 'Detailed' ? 'Concise' : 'Detailed';
                  setCurrentStyle(next);
                }}
                className="bg-slate-800 hover:bg-slate-700 text-brand-300 px-2 py-0.5 rounded border border-slate-700/80 font-mono transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500/50"
                title="Click to toggle concise/detailed"
              >
                Style: {currentStyle}
              </button>

              {/* Examples toggle */}
              <button
                type="button"
                onClick={() => setCurrentExamples(!currentExamples)}
                className={`px-2 py-0.5 rounded border font-mono transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500/50 ${
                  currentExamples
                    ? 'bg-emerald-500/10 text-emerald-600 border-emerald-500/30'
                    : 'bg-slate-800 text-slate-500 border-slate-700/80'
                }`}
                title="Click to toggle examples"
              >
                Examples: {currentExamples ? 'Included' : 'Off'}
              </button>
            </div>

            <div className="text-[11px] text-slate-400 hidden sm:block">
              Subject: <span className="font-semibold text-slate-300">{selectedSubject === 'All' ? 'All my subjects' : selectedSubject}</span>
            </div>
          </div>

          {/* Text Input */}
          <form
            onSubmit={(e) => {
              e.preventDefault();
              handleSend();
            }}
            className="flex items-center space-x-2"
          >
            <input
              type="text"
              value={inputQuery}
              onChange={(e) => setInputQuery(e.target.value)}
              placeholder="Ask a question about your selected subject..."
              disabled={loading}
              aria-label="Your question"
              className={`min-w-0 flex-1 bg-slate-950 border rounded-xl px-4 py-3 text-xs text-slate-100 placeholder-slate-500 focus:outline-none transition-colors shadow-inner ${
                inputQuery.length > MAX_QUESTION_CHARACTERS
                  ? 'border-rose-500/80 focus:border-rose-500'
                  : 'border-slate-800 focus:border-brand-500'
              }`}
            />
            <button
              type="submit"
              disabled={loading || !inputQuery.trim() || inputQuery.length > MAX_QUESTION_CHARACTERS}
              className="bg-brand-600 hover:bg-brand-500 disabled:opacity-40 text-white p-3 rounded-xl shadow-lg shadow-brand-600/20 active:scale-95 transition-all flex-shrink-0"
              title={inputQuery.length > MAX_QUESTION_CHARACTERS ? 'Question exceeds 4,000 character limit' : 'Send question'}
            >
              <Send className="w-4 h-4" />
            </button>
          </form>

          {/* Inline character counter & validation indicator */}
          {inputQuery.length > 0 && (
            <div className="flex items-center justify-between text-[10px] px-1 text-slate-400 font-mono">
              <span className={inputQuery.length > MAX_QUESTION_CHARACTERS ? 'text-rose-500 font-semibold' : ''}>
                {inputQuery.length} / {MAX_QUESTION_CHARACTERS} characters
              </span>
              {inputQuery.length > MAX_QUESTION_CHARACTERS && (
                <span className="text-rose-500 font-sans">Question exceeds 4,000-character maximum</span>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
