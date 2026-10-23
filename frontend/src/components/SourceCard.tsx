import React, { useState } from 'react';
import { BookOpen, ChevronDown, ChevronUp, FileText, ExternalLink } from 'lucide-react';
import { api } from '../services/api';
import { SourceReference } from '../types';

interface SourceCardProps {
  source: SourceReference;
}

const getMethodLabel = (method?: string): string => {
  if (!method) return 'Source';
  switch (method.toLowerCase()) {
    case 'semantic':
      return 'Semantic';
    case 'lexical':
      return 'Keyword';
    case 'hybrid':
      return 'Combined';
    default:
      return method;
  }
};

export const SourceCard: React.FC<SourceCardProps> = ({ source }) => {
  const [pdfError, setPdfError] = useState<string | null>(null);
  const [expanded, setExpanded] = useState(false);
  const methodLabel = getMethodLabel(source.retrieval_method);

  return (
    <div className="bg-slate-800/80 border border-slate-700/80 rounded-lg p-2.5 text-xs hover:border-brand-500/50 transition-colors">
      <div
        className="flex flex-wrap items-center gap-2 select-none"
      >
        <button type="button" aria-expanded={expanded} aria-label={`Show passage from ${source.document_title}, PDF page ${source.page_number}`} onClick={() => setExpanded(!expanded)} className="min-w-0 w-full sm:w-auto sm:flex-1 flex items-center space-x-2 text-left rounded focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500/50">
          <BookOpen className="w-3.5 h-3.5 text-brand-400 flex-shrink-0" />
          <span className="font-semibold text-slate-200 truncate" title={source.document_title}>
            {source.document_title}
          </span>
          <span className="bg-slate-700 text-slate-300 px-1.5 py-0.5 rounded text-[10px] font-mono flex-shrink-0">
            PDF p. {source.page_number}
          </span>
          {expanded ? <ChevronUp className="w-3.5 h-3.5 flex-shrink-0 text-slate-400" /> : <ChevronDown className="w-3.5 h-3.5 flex-shrink-0 text-slate-400" />}
        </button>

        <div className="flex items-center space-x-2 flex-shrink-0">
          <span
            className="px-2 py-0.5 rounded text-[10px] font-medium bg-slate-900/80 text-slate-300 border border-slate-700/60"
            title={source.retrieval_method ? `Retrieved via ${methodLabel} search` : 'Retrieval method was not recorded for this source.'}
          >
            {methodLabel}
          </span>

          <a
            href={`/api/v1/documents/${source.document_id}/download#page=${source.page_number}`}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center space-x-1 text-[10px] text-brand-400 hover:text-brand-300 font-medium px-1.5 py-0.5 rounded bg-slate-900/60 border border-slate-700/60 hover:border-brand-500/50 transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500/50"
            onClick={event => { event.preventDefault(); event.stopPropagation(); setPdfError(null); api.openPdf(source.document_id, source.page_number).catch(error => setPdfError(error.message)); }}
            title={`Open original PDF at physical page ${source.page_number}`}
            aria-label={`View PDF for ${source.document_title} at page ${source.page_number}`}
          >
            <ExternalLink className="w-3 h-3" />
            <span>View PDF</span>
          </a>

        </div>
      </div>

      {pdfError && <p role="alert" className="mt-2 text-rose-400">{pdfError}</p>}
      {expanded && (
        <div className="mt-2 pt-2 border-t border-slate-700/60 text-slate-300 text-[11px] leading-relaxed bg-slate-900/60 p-2 rounded">
          <div className="flex items-center text-slate-400 font-mono text-[10px] mb-1 space-x-1">
            <FileText className="w-3 h-3" />
            <span>Exact Textbook Passage (Chunk #{source.chunk_index}):</span>
          </div>
          <p className="whitespace-pre-wrap break-words">{source.snippet}</p>
        </div>
      )}
    </div>
  );
};
