import React, { useEffect, useState, useRef, useCallback } from 'react';
import { Upload, FileText, Trash2, RefreshCw, CheckCircle, AlertCircle, Clock, BookOpen, ExternalLink, Play, Plus } from 'lucide-react';
import { api } from '../services/api';
import { Document } from '../types';
import { useAuth } from '../context/AuthContext';
import { languageLabel, LANGUAGE_FILTERS } from '../scope';

interface DocumentManagerProps {
  subjects: string[];
  onDocumentCountChange?: () => void;
  onSubjectDeleted?: (subject: string) => void;
}

const DEFAULT_MAX_PDF_BYTES = 52428800; // 50 MiB

export const DocumentManager: React.FC<DocumentManagerProps> = ({ subjects, onDocumentCountChange, onSubjectDeleted }) => {
  const { user, refreshPreferences } = useAuth();
  const [documents, setDocuments] = useState<Document[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [uploading, setUploading] = useState<boolean>(false);
  const [processingId, setProcessingId] = useState<number | null>(null);
  const [maxPdfBytes, setMaxPdfBytes] = useState<number>(DEFAULT_MAX_PDF_BYTES);
  const [selectedSubjectFilter, setSelectedSubjectFilter] = useState<string>('All');

  // Upload Form state
  const [file, setFile] = useState<File | null>(null);
  const [title, setTitle] = useState<string>('');
  const [subject, setSubject] = useState<string>('Java');
  const [newSubject, setNewSubject] = useState('');
  const [addingSubject, setAddingSubject] = useState(false);
  const [subjectError, setSubjectError] = useState<string | null>(null);
  const [createdSubjects, setCreatedSubjects] = useState<string[]>([]);
  const [deletedSubjects, setDeletedSubjects] = useState<string[]>([]);
  const [deletingSubject, setDeletingSubject] = useState<string | null>(null);
  const [subjectToDelete, setSubjectToDelete] = useState<string | null>(null);
  const availableSubjects = [...new Set([...subjects, ...createdSubjects])].filter(name => !deletedSubjects.includes(name));
  const personalSubjects = availableSubjects.filter(name => !LANGUAGE_FILTERS.includes(name));
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [uploadSuccess, setUploadSuccess] = useState<string | null>(null);
  const [actionNotice, setActionNotice] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const fileInputRef = useRef<HTMLInputElement>(null);
  const isPollingRef = useRef<boolean>(false);
  const mountedRef = useRef(false);
  const listController = useRef<AbortController | null>(null);
  const coverageRef = useRef('');

  useEffect(() => {
    mountedRef.current = true;
    return () => { mountedRef.current = false; listController.current?.abort(); };
  }, []);

  const formatFileSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  const fetchDocuments = useCallback(async (filterSub?: string) => {
    if (!mountedRef.current) return;
    listController.current?.abort();
    const controller = new AbortController();
    listController.current = controller;
    try {
      const activeFilter = filterSub !== undefined ? filterSub : selectedSubjectFilter;
      const docs = await api.listDocuments(activeFilter, controller.signal);
      if (!mountedRef.current || controller.signal.aborted) return;
      setDocuments(docs);
      const coverage = JSON.stringify(docs.map(doc => [doc.id, doc.total_chunks, doc.indexing?.embedded_chunks, doc.status]));
      if (coverageRef.current !== coverage) {
        coverageRef.current = coverage;
        onDocumentCountChange?.();
      }
    } catch (err: any) {
      if (mountedRef.current && !controller.signal.aborted) setActionError(err.message || 'Could not load documents.');
    } finally {
      if (mountedRef.current && !controller.signal.aborted) setLoading(false);
    }
  }, [selectedSubjectFilter, onDocumentCountChange]);

  // Initial fetch & health limits
  useEffect(() => {
    let mounted = true;
    const init = async () => {
      try {
        const health = await api.getHealth();
        if (mounted && health.limits?.max_pdf_bytes) {
          setMaxPdfBytes(health.limits.max_pdf_bytes);
        }
      } catch (err) {
        // Fall back to default limit
      }
    };
    init();
    return () => {
      mounted = false;
    };
  }, []);

  useEffect(() => {
    setLoading(true);
    fetchDocuments();
    return () => listController.current?.abort();
  }, [fetchDocuments, user?.id]);

  // Background polling: poll every 2.5s while any document has processing_active === true
  useEffect(() => {
    const hasActiveWorker = documents.some((d) => d.processing_active);
    if (!hasActiveWorker) return;

    const intervalId = setInterval(async () => {
      if (isPollingRef.current) return;
      isPollingRef.current = true;
      try {
        await fetchDocuments();
      } catch (err) {
        console.error('Document polling error:', err);
      } finally {
        isPollingRef.current = false;
      }
    }, 2500);

    return () => clearInterval(intervalId);
  }, [documents, fetchDocuments]);

  const handleAddSubject = async (event: React.FormEvent) => {
    event.preventDefault();
    setAddingSubject(true);
    setSubjectError(null);
    try {
      const created = await api.addSubject(newSubject);
      setCreatedSubjects(previous => [...previous, created.name]);
      setDeletedSubjects(previous => previous.filter(name => name !== created.name));
      setSubject(created.name);
      setNewSubject('');
      onDocumentCountChange?.();
      setActionNotice(`Subject "${created.name}" added. Upload a reference PDF below to start asking questions.`);
    } catch (error: any) {
      setSubjectError(error.message || 'Could not add subject.');
    } finally {
      setAddingSubject(false);
    }
  };

  const handleDeleteSubject = async (name: string) => {
    setDeletingSubject(name);
    setActionError(null);
    setActionNotice(null);
    setUploadSuccess(null);
    try {
      const result = await api.deleteSubject(name);
      if (!mountedRef.current) return;
      setDeletedSubjects(previous => [...previous, name]);
      setCreatedSubjects(previous => previous.filter(value => value !== name));
      if (subject === name) setSubject('Java');
      setSelectedSubjectFilter('All');
      onSubjectDeleted?.(name);
      setActionNotice(result.message);
      if (result.storage_cleanup_pending) setActionError(result.message);
      await fetchDocuments('All');
      try { await refreshPreferences(); } catch { setActionError('Subject deleted. Reload to refresh your saved preferences.'); }
      onDocumentCountChange?.();
    } catch (error: any) {
      if (!mountedRef.current) return;
      setActionError(error.message || 'Could not delete subject.');
    } finally {
      if (mountedRef.current) {
        setDeletingSubject(null);
        setSubjectToDelete(null);
      }
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const selectedFile = e.target.files[0];
      if (!selectedFile.name.toLowerCase().endsWith('.pdf')) {
        setUploadError('Only PDF files are supported.');
        setFile(null);
        return;
      }
      if (selectedFile.size > maxPdfBytes) {
        setUploadError(`File exceeds maximum size of ${formatFileSize(maxPdfBytes)}.`);
        setFile(null);
        return;
      }
      setFile(selectedFile);
      setUploadError(null);
      if (!title) {
        setTitle(selectedFile.name.replace(/\.pdf$/i, ''));
      }
    }
  };

  const handleUpload = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file) {
      setUploadError('Please select a PDF document to upload.');
      return;
    }

    if (file.size > maxPdfBytes) {
      setUploadError(`File exceeds maximum size of ${formatFileSize(maxPdfBytes)}.`);
      return;
    }

    setUploading(true);
    setUploadError(null);
    setUploadSuccess(null);
    setActionNotice(null);
    setActionError(null);

    try {
      const res = await api.uploadDocument(file, title, subject, true);
      if (res.processing_scheduled) {
        setUploadSuccess(res.message);
      } else {
        setUploadSuccess(
          `${res.message} Background worker is currently busy; click Process on the document row to resume indexing.`
        );
      }

      setFile(null);
      setTitle('');
      if (fileInputRef.current) fileInputRef.current.value = '';
      await fetchDocuments();
    } catch (err: any) {
      setUploadError(err.message || 'Failed to upload document.');
      await fetchDocuments(); // A lost response may follow a successful save.
    } finally {
      setUploading(false);
    }
  };

  const handleProcess = async (docId: number) => {
    setProcessingId(docId);
    setActionError(null);
    setActionNotice(null);

    try {
      const res = await api.processDocument(docId);
      setActionNotice(res.message);
      await fetchDocuments();
    } catch (err: any) {
      setActionError(err.message || 'Error triggering document processing.');
      await fetchDocuments();
    } finally {
      setProcessingId(null);
    }
  };

  const handleDelete = async (docId: number, docTitle: string) => {
    if (!confirm(`Are you sure you want to delete "${docTitle}" and all its indexed chunks?`)) {
      return;
    }
    setActionError(null);
    setActionNotice(null);

    try {
      const res = await api.deleteDocument(docId);
      setActionNotice(res.message || `Document "${docTitle}" was deleted.`);
      if (res.storage_cleanup_pending) setActionError(res.message);
      await fetchDocuments();
    } catch (err: any) {
      setActionError(err.message || 'Error deleting document.');
      await fetchDocuments();
    }
  };

  const handleFilterChange = (newSubject: string) => {
    setSelectedSubjectFilter(newSubject);
  };

  return (
    <div className="flex-1 min-w-0 overflow-y-auto p-4 md:p-8 space-y-8 max-w-6xl mx-auto w-full">
      {/* Top Banner */}
      <div>
        <h1 className="text-2xl font-black text-slate-100 tracking-tight flex items-center space-x-2.5">
          <BookOpen className="w-6 h-6 text-brand-400" />
          <span>My Book Library</span>
        </h1>
        <p className="text-xs text-slate-400 mt-1 max-w-2xl leading-relaxed">
          C, C++, Java, and Python are included for everyone. Add your own subjects and reference books below.
          Your added subjects and PDFs are private to your account. Process a book before asking about it.
        </p>
      </div>

      {user && <section className="bg-slate-900 border border-slate-800 rounded-2xl p-4 sm:p-6 space-y-3">
        <form onSubmit={handleAddSubject} className="space-y-3">
        <h2 className="text-sm font-bold text-slate-200">Add subject</h2>
        <p className="text-xs text-slate-400">Create a personal subject such as Biology or Operating Systems, then upload its reference book.</p>
        <div className="flex flex-col sm:flex-row gap-3">
          <input aria-label="New subject name" value={newSubject} onChange={event => setNewSubject(event.target.value)} maxLength={100}
            placeholder="Enter subject name" required disabled={addingSubject || Boolean(deletingSubject)}
            className="min-w-0 flex-1 bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-sm" />
          <button type="submit" disabled={addingSubject || Boolean(deletingSubject) || !newSubject.trim()} className="flex items-center justify-center gap-2 bg-brand-600 text-white px-4 py-2 rounded-xl text-xs disabled:opacity-40">
            <Plus className="w-4 h-4" />{addingSubject ? 'Adding...' : 'Add subject'}
          </button>
        </div>
        {subjectError && <p role="alert" className="text-xs text-rose-400">{subjectError}</p>}
        </form>
        {personalSubjects.length > 0 && <div className="border-t border-slate-800 pt-4 space-y-2">
          <h2 className="text-sm font-bold text-slate-200">My personal subjects</h2>
          <p className="text-xs text-slate-400">Delete a subject and all its source books, or delete individual books in the list below. The four default subjects stay included.</p>
          {personalSubjects.map(name => <div key={name} className="flex min-w-0 items-center justify-between gap-3 rounded-xl bg-slate-950 px-3 py-2">
            <span className="min-w-0 break-words text-xs text-slate-200">{name}</span>
            <button type="button" aria-label={`Delete subject ${name}`} onClick={() => setSubjectToDelete(name)}
              disabled={Boolean(deletingSubject) || uploading || addingSubject}
              className="flex flex-shrink-0 items-center gap-1.5 text-xs text-rose-500 hover:text-rose-400 disabled:opacity-40">
              <Trash2 className="w-3.5 h-3.5" />{deletingSubject === name ? 'Deleting...' : 'Delete subject'}
            </button>
          </div>)}
        </div>}
      </section>}

      {/* Upload Box */}
      <div className="bg-slate-900 border border-slate-800 rounded-2xl p-4 sm:p-6 shadow-xl">
        <h2 className="text-sm font-bold text-slate-200 mb-4 flex items-center space-x-2">
          <Upload className="w-4 h-4 text-brand-400" />
          <span>Upload Reference Book</span>
        </h2>

        {uploadError && (
          <div className="mb-4 p-3 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-500 text-xs flex items-center space-x-2">
            <AlertCircle className="w-4 h-4 flex-shrink-0" />
            <span>{uploadError}</span>
          </div>
        )}

        {uploadSuccess && (
          <div className="mb-4 p-3 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-600 text-xs flex items-center space-x-2">
            <CheckCircle className="w-4 h-4 flex-shrink-0" />
            <span>{uploadSuccess}</span>
          </div>
        )}

        {!user && (
          <div className="mb-4 p-3 rounded-xl bg-brand-100/70 border border-brand-200 text-brand-800 text-xs">
            Sign in to add, reprocess, or remove books. You can still browse and search the shared study library below.
          </div>
        )}

        <form onSubmit={handleUpload} className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {/* File input */}
            <div className="md:col-span-1">
              <label className="block text-xs font-semibold text-slate-300 mb-1.5">
                PDF File <span className="text-[10px] text-slate-400 font-normal">(&le; {formatFileSize(maxPdfBytes)})</span>
              </label>
              <input
                ref={fileInputRef}
                type="file"
                accept=".pdf"
                onChange={handleFileChange}
                disabled={uploading || !user}
                className="w-full text-xs text-slate-400 file:mr-3 file:py-2 file:px-3 file:rounded-lg file:border-0 file:text-xs file:font-semibold file:bg-brand-600 file:text-white hover:file:bg-brand-500 cursor-pointer bg-slate-950 border border-slate-800 rounded-xl p-1.5 focus:outline-none disabled:opacity-50"
              />
            </div>

            {/* Title */}
            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1.5">Book / Document Title</label>
              <input
                type="text"
                placeholder="e.g. Core Java Volume I"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                disabled={uploading || !user}
                className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-xs text-slate-200 focus:outline-none focus:border-brand-500 disabled:opacity-50"
              />
            </div>

            {/* Subject */}
            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1.5">Subject</label>
              <select
                value={subject}
                onChange={(e) => setSubject(e.target.value)}
                disabled={uploading || !user}
                className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-xs text-slate-200 focus:outline-none focus:border-brand-500 cursor-pointer disabled:opacity-50"
              >
                {availableSubjects
                  .filter((s) => s !== 'All')
                  .map((sub) => (
                    <option key={sub} value={sub}>
                      {sub}
                    </option>
                  ))}
              </select>
            </div>
          </div>

          <p className="text-[11px] text-slate-400">Processing sends book text to Google Gemini for search and answers. Your PDFs stay private from other TechQuery users.</p>
          <div className="flex justify-end pt-2">
            <button
              type="submit"
              disabled={uploading || !file || !user}
              className="flex items-center space-x-2 bg-brand-600 hover:bg-brand-500 disabled:opacity-40 text-white font-semibold text-xs px-5 py-2.5 rounded-xl shadow-lg shadow-brand-600/20 active:scale-95 transition-all"
            >
              <Upload className="w-3.5 h-3.5" />
              <span>{uploading ? 'Uploading PDF Document...' : 'Upload & Process Book'}</span>
            </button>
          </div>
        </form>
      </div>

      {/* Documents Table */}
      <div className="bg-slate-900 border border-slate-800 rounded-2xl p-4 sm:p-6 shadow-xl space-y-4">
        {/* Table Header and Filter */}
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="text-sm font-bold text-slate-200">Saved PDF Books</h2>
            <p className="text-[11px] text-slate-400">Total Books: {documents.length}</p>
          </div>

          <div className="flex min-w-0 w-full sm:w-auto items-center gap-2">
            <div className="flex min-w-0 flex-1 items-center space-x-1.5 bg-slate-950 border border-slate-800 rounded-lg px-2.5 py-1 text-xs">
              <span className="text-slate-500 text-[11px]">Filter:</span>
              <select
                value={selectedSubjectFilter}
                onChange={(e) => handleFilterChange(e.target.value)}
                aria-label="Filter documents by subject"
                className="min-w-0 w-full bg-transparent text-slate-200 text-xs font-medium focus:outline-none cursor-pointer"
              >
                {availableSubjects.map((sub) => (
                  <option key={sub} value={sub} className="bg-slate-900 text-slate-200">
                    {languageLabel(sub)}
                  </option>
                ))}
              </select>
            </div>

            <button
              onClick={() => fetchDocuments()}
              disabled={loading}
              className="flex flex-shrink-0 items-center space-x-1.5 text-xs text-slate-400 hover:text-slate-200 bg-slate-800 hover:bg-slate-700/80 px-3 py-1.5 rounded-lg transition-colors"
              title="Refresh document status"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
              <span>Refresh</span>
            </button>
          </div>
        </div>

        {/* Action feedback notifications */}
        {actionNotice && (
          <div className="p-3 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-600 text-xs flex items-center justify-between">
            <span>{actionNotice}</span>
            <button onClick={() => setActionNotice(null)} className="text-xs hover:text-emerald-700 font-bold ml-2">
              &times;
            </button>
          </div>
        )}

        {actionError && (
          <div className="p-3 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-500 text-xs flex items-center justify-between">
            <span>{actionError}</span>
            <button onClick={() => setActionError(null)} className="text-xs hover:text-rose-700 font-bold ml-2">
              &times;
            </button>
          </div>
        )}

        {loading ? (
          <div className="text-center py-12 text-slate-400 text-xs">Loading documents...</div>
        ) : documents.length === 0 ? (
          <div className="text-center py-12 text-slate-400 text-xs">
            <FileText className="w-8 h-8 mx-auto mb-2 opacity-30 text-slate-400" />
            <p className="font-semibold text-slate-300">No documents found.</p>
            <p className="text-[11px] text-slate-400 mt-1">Upload a reference PDF for your subject, or choose another subject filter.</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="border-b border-slate-800 text-slate-400 font-semibold uppercase text-[10px] tracking-wider">
                  <th className="pb-3 px-3">Title &amp; Filename</th>
                  <th className="pb-3 px-3">Subject</th>
                  <th className="pb-3 px-3">Size</th>
                  <th className="pb-3 px-3">Pages / Chunks</th>
                  <th className="pb-3 px-3">Status</th>
                  <th className="pb-3 px-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60">
                {documents.map((doc) => {
                  const isProcessingThis = processingId === doc.id;
                  const canModify = Boolean(doc.can_modify);
                  const isBusy = Boolean(doc.processing_active || isProcessingThis);

                  return (
                    <tr key={doc.id} className="hover:bg-slate-800/40 transition-colors">
                      <td className="py-3 px-3">
                        <div className="flex items-center space-x-2.5">
                          <FileText className="w-4 h-4 text-brand-400 flex-shrink-0" />
                          <div className="truncate max-w-xs">
                            <p className="font-bold text-slate-200 truncate">{doc.title}</p>
                            <p className="text-[10px] text-slate-400">{doc.is_default ? 'Included for everyone' : 'Private · Only you'}</p>
                            <div className="flex items-center space-x-2">
                              <span className="text-[10px] text-slate-400 font-mono truncate">{doc.original_filename}</span>
                              <a
                                href={`/api/v1/documents/${doc.id}/download`}
                                onClick={event => { event.preventDefault(); api.openPdf(doc.id).catch(error => setActionError(error.message)); }}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="text-brand-500 hover:text-brand-400 text-[10px] inline-flex items-center space-x-0.5"
                                title="View PDF inline"
                              >
                                <ExternalLink className="w-2.5 h-2.5" />
                                <span>PDF</span>
                              </a>
                            </div>
                          </div>
                        </div>
                      </td>

                      <td className="py-3 px-3">
                        <span className="bg-slate-800 text-slate-300 px-2 py-0.5 rounded-full text-[10px] font-medium border border-slate-700/60">
                          {doc.subject}
                        </span>
                      </td>

                      <td className="py-3 px-3 text-slate-400 font-mono text-[11px]">
                        {formatFileSize(doc.file_size)}
                      </td>

                      <td className="py-3 px-3">
                        <div className="flex items-center space-x-2 text-[11px] font-mono">
                          <span className="text-slate-300">{doc.total_pages} pgs</span>
                          <span className="text-slate-600">/</span>
                          <span className="text-brand-400 font-semibold">{doc.total_chunks} chunks</span>
                        </div>
                        {doc.indexing?.extraction && !doc.indexing.extraction.complete && doc.indexing.extraction.total_pages > 0 && (
                          <p className="mt-1 text-[10px] text-slate-400">Pages saved: {doc.indexing.extraction.saved_pages}/{doc.indexing.extraction.total_pages}</p>
                        )}
                      </td>

                      <td className="py-3 px-3">
                        {(doc.in_scope === false) ? (
                          <span className="text-slate-400 text-[11px]" title="PDF retained; excluded from answers and indexing">Outside scope · retained</span>
                        ) : <>
                        {/* Ready: complete semantic and lexical indexing */}
                        {doc.status === 'ready' && (
                          <span className="inline-flex items-center space-x-1 text-emerald-600 bg-emerald-500/10 border border-emerald-500/20 px-2 py-0.5 rounded-full text-[10px] font-medium">
                            <CheckCircle className="w-3 h-3" />
                            <span>Ready</span>
                          </span>
                        )}

                        {/* Partial: text extracted & searchable lexically; vector indexing partial */}
                        {doc.status === 'partial' && (
                          <span
                            className="inline-flex items-center space-x-1 text-brand-700 bg-brand-500/10 border border-brand-500/20 px-2 py-0.5 rounded-full text-[10px] font-medium"
                            title={`Lexical search active. Vector embeddings: ${doc.indexing?.embedded_chunks ?? 0} of ${doc.total_chunks} chunks`}
                          >
                            <Clock className="w-3 h-3" />
                            <span>
                              Partial ({doc.indexing?.embedded_chunks ?? 0}/{doc.total_chunks})
                            </span>
                          </span>
                        )}

                        {/* Processing: actively chunking or embedding */}
                        {doc.status === 'processing' && (
                          <span className="inline-flex items-center space-x-1 text-brand-500 bg-brand-500/10 border border-brand-500/20 px-2 py-0.5 rounded-full text-[10px] font-medium animate-pulse">
                            <RefreshCw className="w-3 h-3 animate-spin" />
                            <span>{doc.indexing?.extraction && !doc.indexing.extraction.complete ? 'Reading PDF' : 'Indexing'}</span>
                          </span>
                        )}

                        {/* Pending: uploaded, waiting for worker */}
                        {doc.status === 'pending' && (
                          <span className="inline-flex items-center space-x-1 text-amber-600 bg-amber-500/10 border border-amber-500/20 px-2 py-0.5 rounded-full text-[10px] font-medium">
                            <Clock className="w-3 h-3" />
                            <span>{doc.processing_active ? 'Queued' : doc.error_message ? 'Resume available' : 'Pending'}</span>
                          </span>
                        )}

                        {/* Error: extraction or embedding failure */}
                        {doc.status === 'error' && (
                          <span
                            className="inline-flex items-center space-x-1 text-rose-500 bg-rose-500/10 border border-rose-500/20 px-2 py-0.5 rounded-full text-[10px] font-medium cursor-help"
                            title={doc.error_message || 'Processing failed'}
                          >
                            <AlertCircle className="w-3 h-3" />
                            <span>Error</span>
                          </span>
                        )}
                        {!isBusy && doc.error_message && <p className="mt-1 max-w-56 text-[10px] text-slate-400">{doc.error_message}</p>}

                        {/* Neutral fallback for unknown status values */}
                        {!['ready', 'partial', 'processing', 'pending', 'error'].includes(doc.status) && (
                          <span className="inline-flex items-center space-x-1 text-slate-400 bg-slate-800 border border-slate-700/60 px-2 py-0.5 rounded-full text-[10px] font-medium">
                            <span>{doc.status}</span>
                          </span>
                        )}
                        </>}
                        {doc.indexing?.provider_use_allowed === false && (
                          <p className="mt-1 text-[10px] text-slate-400">Local passages only</p>
                        )}
                      </td>

                      <td className="py-3 px-3 text-right">
                        <div className="flex items-center justify-end space-x-1.5">
                          {/* Process / Resume button */}
                          <button
                            onClick={() => handleProcess(doc.id)}
                            disabled={!canModify || isBusy || doc.in_scope === false || doc.indexing?.provider_use_allowed === false}
                            title={
                              doc.indexing?.provider_use_allowed === false
                                ? 'Local passages are searchable; Google use is awaiting permission'
                                : doc.in_scope === false
                                ? 'This book cannot be indexed'
                                : !canModify
                                ? 'Only your own books can be processed; default books are maintained for everyone'
                                : isBusy
                                ? 'Processing is currently active'
                                : doc.status === 'partial'
                                ? 'Resume embedding batch (bounded work)'
                                : 'Process document'
                            }
                            aria-label={`Process document ${doc.title}`}
                            className={`p-1.5 rounded-lg transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500/50 ${
                              canModify && !isBusy && doc.in_scope !== false && doc.indexing?.provider_use_allowed !== false
                                ? 'text-slate-400 hover:text-brand-400 hover:bg-slate-800'
                                : 'text-slate-600 opacity-40 cursor-not-allowed'
                            }`}
                          >
                            {doc.status === 'partial' ? (
                              <Play className={`w-3.5 h-3.5 ${isBusy ? 'animate-pulse' : ''}`} />
                            ) : (
                              <RefreshCw className={`w-3.5 h-3.5 ${isBusy ? 'animate-spin' : ''}`} />
                            )}
                          </button>

                          {/* Delete button */}
                          <button
                            onClick={() => handleDelete(doc.id, doc.title)}
                            disabled={!canModify || isBusy || doc.is_default}
                            title={
                              doc.is_default
                                ? 'Default books are included for every account'
                                : !canModify
                                ? 'Only your own books can be deleted'
                                : isBusy
                                ? 'Cannot delete while processing is active'
                                : 'Delete document & chunks'
                            }
                            aria-label={`Delete document ${doc.title}`}
                            className={`p-1.5 rounded-lg transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-rose-500/50 ${
                              canModify && !isBusy && !doc.is_default
                                ? 'text-slate-400 hover:text-rose-500 hover:bg-slate-800'
                                : 'text-slate-600 opacity-40 cursor-not-allowed'
                            }`}
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
      {subjectToDelete && <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 p-4"
        onClick={() => { if (!deletingSubject) setSubjectToDelete(null); }}>
        <div role="dialog" aria-modal="true" aria-labelledby="delete-subject-title"
          className="w-full max-w-md max-h-[calc(100dvh-2rem)] overflow-y-auto rounded-2xl border border-slate-800 bg-slate-900 p-5 space-y-4 shadow-xl"
          onClick={event => event.stopPropagation()}
          onKeyDown={event => {
            if (event.key === 'Escape' && !deletingSubject) setSubjectToDelete(null);
            if (event.key === 'Tab') {
              const buttons = event.currentTarget.querySelectorAll<HTMLButtonElement>('button:not(:disabled)');
              const first = buttons[0], last = buttons[buttons.length - 1];
              if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus(); }
              if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
            }
          }}>
          <h2 id="delete-subject-title" className="text-base font-bold text-slate-100">Delete personal subject?</h2>
          <p className="text-sm text-slate-300 break-words">This permanently removes <strong>{subjectToDelete}</strong>, all its uploaded source books, and their search data. This cannot be undone.</p>
          <p className="text-xs text-slate-400">Previous conversations stay in your history. The four default subjects and books stay included.</p>
          <div className="flex flex-wrap justify-end gap-3">
            <button type="button" autoFocus disabled={Boolean(deletingSubject)} onClick={() => setSubjectToDelete(null)}
              className="rounded-xl bg-slate-800 px-4 py-2 text-xs text-slate-200 disabled:opacity-40">Cancel</button>
            <button type="button" disabled={Boolean(deletingSubject)} onClick={() => handleDeleteSubject(subjectToDelete)}
              className="rounded-xl bg-rose-600 px-4 py-2 text-xs font-semibold text-white disabled:opacity-40">
              {deletingSubject ? 'Deleting...' : 'Confirm delete subject'}
            </button>
          </div>
        </div>
      </div>}
    </div>
  );
};
