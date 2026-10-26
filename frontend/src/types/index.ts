export type ExplanationLevel = 'Beginner' | 'Intermediate' | 'Advanced';
export type AnswerStyle = 'Concise' | 'Detailed';

export interface User {
  id: number;
  email: string;
  username: string;
  is_active: boolean;
  role: string;
  created_at: string;
}

export interface UserPreference {
  id?: number;
  user_id?: number;
  explanation_level: ExplanationLevel;
  answer_style: AnswerStyle;
  include_examples: boolean;
  preferred_subject: string;
  updated_at?: string;
}

export type DocumentStatus = 'pending' | 'processing' | 'partial' | 'ready' | 'error' | string;

export interface DocumentIndexing {
  extraction?: { total_pages: number; saved_pages: number; complete: boolean; extractor: string | null };
  provider_use_allowed?: boolean;
  total_chunks: number;
  embedded_chunks: number;
  missing_embeddings: number;
  unverified_embeddings: number;
  embedding_model: string;
  embedding_dimensions: number;
  semantic_ready: boolean;
}

export interface Document {
  id: number;
  title: string;
  filename: string;
  original_filename: string;
  file_size: number;
  subject: string;
  total_pages: number;
  total_chunks: number;
  status: DocumentStatus;
  error_message?: string | null;
  uploaded_by?: number | null;
  created_at: string;
  indexing?: DocumentIndexing;
  is_default: boolean;
  can_modify: boolean;
  processing_active: boolean;
  in_scope: boolean;
}

export interface DocumentUploadResponse {
  message: string;
  document: Document;
  processing_scheduled: boolean;
}

export interface DocumentProcessResponse {
  message: string;
  document_id: number;
  chunks_created: number;
  pages_processed: number;
  status: string;
  indexing: DocumentIndexing;
}

export type RetrievalMethod = 'semantic' | 'lexical' | 'hybrid' | string;

export interface SourceReference {
  document_id: number;
  document_title: string;
  page_number: number;
  chunk_index: number;
  similarity_score: number;
  snippet: string;
  retrieval_method?: RetrievalMethod;
}

export type ResponseMode = 'generated' | 'general_ai' | 'source_excerpts' | 'abstained' | string;
export type RetrievalMode = 'semantic' | 'lexical' | 'hybrid' | 'none' | string;

export interface Message {
  id: number;
  conversation_id: number;
  role: 'user' | 'assistant';
  content: string;
  sources?: SourceReference[] | null;
  created_at: string;
  suggested_questions?: string[];
  response_mode?: ResponseMode | null;
  retrieval_mode?: RetrievalMode | null;
  abstained?: boolean | null;
}

export interface Conversation {
  id: number;
  user_id: number;
  title: string;
  subject: string;
  created_at: string;
  updated_at: string;
  messages?: Message[];
}

export interface QueryResponse {
  answer: string;
  sources: SourceReference[];
  context_used: boolean;
  conversation_id?: number;
  message_id?: number;
  preferences_applied: {
    explanation_level: ExplanationLevel;
    answer_style: AnswerStyle;
    include_examples: boolean;
  };
  suggested_questions: string[];
  response_mode?: ResponseMode;
  retrieval_mode?: RetrievalMode;
  abstained?: boolean;
}

export interface SystemHealth {
  status: string;
  app_name: string;
  version: string;
  limits: {
    max_pdf_bytes: number;
    max_question_characters: number;
  };
  database: {
    status: string;
    type: string;
    total_documents: number;
    total_indexed_chunks: number;
    total_embedded_chunks: number;
    semantic_ready_documents: number;
    unverified_embeddings: number;
  };
  gemini: {
    configured: boolean;
    model: string;
    embedding_model: string;
    instructions: string;
    availability?: string;
  };
}
