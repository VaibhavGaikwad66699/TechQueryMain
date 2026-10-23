import React, { useState, useEffect } from 'react';
import { X, Check, Sliders, Code } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { AnswerStyle, ExplanationLevel } from '../types';
import { languageFilter, languageLabel } from '../scope';

interface PreferencesModalProps {
  isOpen: boolean;
  onClose: () => void;
  subjects: string[];
}

export const PreferencesModal: React.FC<PreferencesModalProps> = ({ isOpen, onClose, subjects }) => {
  const { preferences, updatePreferences } = useAuth();

  const [level, setLevel] = useState<ExplanationLevel>(preferences.explanation_level);
  const [style, setStyle] = useState<AnswerStyle>(preferences.answer_style);
  const [examples, setExamples] = useState<boolean>(preferences.include_examples);
  const [subject, setSubject] = useState<string>(languageFilter(preferences.preferred_subject));
  const [isSaving, setIsSaving] = useState(false);
  const [savedSuccess, setSavedSuccess] = useState(false);

  useEffect(() => {
    if (isOpen) {
      setLevel(preferences.explanation_level);
      setStyle(preferences.answer_style);
      setExamples(preferences.include_examples);
      setSubject(languageFilter(preferences.preferred_subject));
    }
  }, [isOpen, preferences]);

  if (!isOpen) return null;

  const handleSave = async () => {
    setIsSaving(true);
    try {
      await updatePreferences({
        explanation_level: level,
        answer_style: style,
        include_examples: examples,
        preferred_subject: subject,
      });
      setSavedSuccess(true);
      setTimeout(() => {
        setSavedSuccess(false);
        onClose();
      }, 700);
    } catch (err) {
      alert('Failed to save preferences.');
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div
      onClick={onClose}
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm select-none"
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-label="Learning preferences"
        onClick={(e) => e.stopPropagation()}
        className="bg-slate-900 border border-slate-800 rounded-2xl w-full max-w-lg max-h-[calc(100dvh-2rem)] flex flex-col shadow-2xl overflow-hidden animate-in fade-in zoom-in-95 duration-150"
      >
        {/* Header */}
        <div className="p-5 flex-shrink-0 border-b border-slate-800 flex items-center justify-between bg-slate-950/40">
          <div className="flex items-center space-x-2.5">
            <div className="w-8 h-8 rounded-lg bg-brand-500/10 text-brand-400 flex items-center justify-center">
              <Sliders className="w-4 h-4" />
            </div>
            <div>
              <h3 className="font-bold text-slate-100 text-sm">Learning preferences</h3>
              <p className="text-[11px] text-slate-400">Choose how answers are shaped from your study library</p>
            </div>
          </div>
          <button aria-label="Close preferences" onClick={onClose} className="text-slate-400 hover:text-slate-200 p-1 rounded-lg">
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Form Body */}
        <div className="p-4 sm:p-5 space-y-5 min-h-0 overflow-y-auto">
          {/* Explanation Level */}
          <div>
            <label className="text-xs font-semibold text-slate-300 block mb-2 flex items-center justify-between">
              <span>Explanation Level</span>
              <span className="text-[10px] text-brand-400 font-mono">Current: {level}</span>
            </label>
            <div className="grid grid-cols-3 gap-2">
              {(['Beginner', 'Intermediate', 'Advanced'] as ExplanationLevel[]).map((lvl) => (
                <button
                  key={lvl}
                  type="button"
                  onClick={() => setLevel(lvl)}
                  className={`p-3 rounded-xl border text-left transition-all ${
                    level === lvl
                      ? 'border-brand-500 bg-brand-500/10 text-brand-800 shadow-sm'
                      : 'border-slate-800 bg-slate-950/40 text-slate-400 hover:border-slate-700 hover:text-slate-200'
                  }`}
                >
                  <p className="font-bold text-xs">{lvl}</p>
                  <p className="text-[10px] text-slate-400 mt-1 leading-tight">
                    {lvl === 'Beginner' && 'Foundational concepts & simple analogies'}
                    {lvl === 'Intermediate' && 'Practical explanations & algorithms'}
                    {lvl === 'Advanced' && 'Low-level internals & performance trade-offs'}
                  </p>
                </button>
              ))}
            </div>
          </div>

          {/* Answer Style */}
          <div>
            <label className="text-xs font-semibold text-slate-300 block mb-2">Answer Style</label>
            <div className="grid grid-cols-2 gap-2">
              {(['Concise', 'Detailed'] as AnswerStyle[]).map((stl) => (
                <button
                  key={stl}
                  type="button"
                  onClick={() => setStyle(stl)}
                  className={`p-3 rounded-xl border text-left transition-all ${
                    style === stl
                      ? 'border-brand-500 bg-brand-500/10 text-brand-800 shadow-sm'
                      : 'border-slate-800 bg-slate-950/40 text-slate-400 hover:border-slate-700 hover:text-slate-200'
                  }`}
                >
                  <p className="font-bold text-xs">{stl}</p>
                  <p className="text-[10px] text-slate-400 mt-1">
                    {stl === 'Concise' ? 'Fast, high-yield bulleted summary' : 'Comprehensive chapter-like walkthrough'}
                  </p>
                </button>
              ))}
            </div>
          </div>

          {/* Code Examples Toggle */}
          <div className="bg-slate-950/50 border border-slate-800 p-3.5 rounded-xl flex items-center justify-between">
            <div className="flex items-center space-x-3">
              <div className="w-8 h-8 rounded-lg bg-emerald-500/10 text-emerald-400 flex items-center justify-center">
                <Code className="w-4 h-4" />
              </div>
              <div>
                <p className="text-xs font-semibold text-slate-200">Include Examples</p>
                <p className="text-[11px] text-slate-400">Include examples supported by your selected books</p>
              </div>
            </div>
            <button
              type="button"
              aria-label="Include examples"
              aria-pressed={examples}
              onClick={() => setExamples(!examples)}
              className={`w-11 h-6 rounded-full transition-colors relative flex items-center px-0.5 ${
                examples ? 'bg-brand-600' : 'bg-slate-700'
              }`}
            >
              <div
                className={`w-5 h-5 rounded-full bg-white transition-transform ${
                  examples ? 'translate-x-5' : 'translate-x-0'
                }`}
              />
            </button>
          </div>

          {/* Preferred Subject */}
          <div>
            <label className="text-xs font-semibold text-slate-300 block mb-2">Preferred subject</label>
            <select
              value={subject}
              onChange={(e) => setSubject(e.target.value)}
              className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-xs text-slate-200 focus:outline-none focus:border-brand-500"
            >
              {subjects.map((sub) => (
                <option key={sub} value={sub}>
                  {languageLabel(sub)}
                </option>
              ))}
            </select>
          </div>
        </div>

        {/* Footer */}
        <div className="p-4 flex-shrink-0 border-t border-slate-800 bg-slate-950/60 flex items-center justify-end space-x-2">
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2 text-xs text-slate-400 hover:text-slate-200 transition-colors"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={handleSave}
            disabled={isSaving}
            className="flex items-center space-x-1.5 bg-brand-600 hover:bg-brand-500 text-white font-semibold text-xs px-4 py-2 rounded-lg shadow-md shadow-brand-600/20 active:scale-95 transition-all"
          >
            {savedSuccess ? (
              <>
                <Check className="w-3.5 h-3.5 text-emerald-300" />
                <span>Saved!</span>
              </>
            ) : (
              <>
                <span>{isSaving ? 'Saving...' : 'Apply Preferences'}</span>
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
};
