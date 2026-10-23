import {
  Document,
  DocumentUploadResponse,
  DocumentProcessResponse,
  Conversation,
  Message,
  QueryResponse,
  SystemHealth,
  User,
  UserPreference,
} from '../types';

const API_BASE = '/api/v1';
const REQUEST_TIMEOUT_MS = 30000;
const UPLOAD_TIMEOUT_MS = 300000;
// Allow the default embedding retries plus two 30-second generation attempts.
const ANSWER_TIMEOUT_MS = 120000;

function extractErrorMessage(response: Response, errorData: any): string {
  if (errorData && typeof errorData === 'object') {
    // 1. Prefer nonempty message
    if (typeof errorData.message === 'string' && errorData.message.trim()) {
      return errorData.message.trim();
    }

    // 2. Then string detail
    if (typeof errorData.detail === 'string' && errorData.detail.trim()) {
      return errorData.detail.trim();
    }

    // 3. Then validation-array msg strings (e.g. FastAPI / Pydantic 422 error detail)
    if (Array.isArray(errorData.detail) && errorData.detail.length > 0) {
      const messages = errorData.detail
        .map((item: any) => {
          if (item && typeof item === 'object') {
            return typeof item.msg === 'string' ? item.msg : typeof item.message === 'string' ? item.message : '';
          }
          return typeof item === 'string' ? item : '';
        })
        .filter(Boolean);

      if (messages.length > 0) {
        return messages.join('; ');
      }
    }
  }

  // 4. Fall back to a short status message
  return response.statusText
    ? `Request failed (${response.status}: ${response.statusText})`
    : `Request failed with status ${response.status}`;
}

class ApiService {
  private token: string | null = null;

  constructor() {
    this.token = localStorage.getItem('techquery_token');
  }

  setToken(token: string | null) {
    this.token = token;
    if (token) {
      localStorage.setItem('techquery_token', token);
    } else {
      localStorage.removeItem('techquery_token');
    }
  }

  getToken(): string | null {
    return this.token;
  }

  private async request<T>(endpoint: string, options: RequestInit = {}, timeoutMs = REQUEST_TIMEOUT_MS): Promise<T> {
    const url = `${API_BASE}${endpoint}`;
    const headers = new Headers(options.headers || {});

    if (this.token && !headers.has('Authorization')) {
      headers.set('Authorization', `Bearer ${this.token}`);
    }

    if (!(options.body instanceof FormData) && !headers.has('Content-Type')) {
      headers.set('Content-Type', 'application/json');
    }

    const controller = new AbortController();
    let timedOut = false;
    const timeoutId = setTimeout(() => { timedOut = true; controller.abort(); }, timeoutMs);
    const cancel = () => controller.abort();
    options.signal?.addEventListener('abort', cancel, { once: true });
    if (options.signal?.aborted) cancel();
    try {
      const response = await fetch(url, {
        ...options,
        headers,
        signal: controller.signal,
      });
      if (!response.ok) {
        let errorData: unknown = null;
        try { errorData = await response.json(); } catch (err) {
          if (controller.signal.aborted) throw err;
        }
        throw new Error(extractErrorMessage(response, errorData));
      }
      // Keep the timeout active while receiving/parsing the body too.
      return await response.json();
    } catch (err: any) {
      if (timedOut) throw new Error('Request timed out. The server may still finish this action; refresh before retrying.');
      if (options.signal?.aborted) throw new DOMException('Request canceled.', 'AbortError');
      if (err instanceof TypeError) throw new Error('Could not connect to TechQuery. Check your connection and retry.');
      if (err instanceof SyntaxError) throw new Error('The server returned an unreadable response. Please retry.');
      throw err instanceof Error ? err : new Error('Network error connecting to TechQuery API.');
    } finally {
      clearTimeout(timeoutId);
      options.signal?.removeEventListener('abort', cancel);
    }
  }

  // Health
  async getHealth(): Promise<SystemHealth> {
    return this.request<SystemHealth>('/health');
  }

  async getSubjects(): Promise<string[]> {
    return this.request<string[]>('/subjects');
  }

  async addSubject(name: string): Promise<{ id: number; name: string }> {
    return this.request('/subjects', { method: 'POST', body: JSON.stringify({ name }) });
  }

  async deleteSubject(name: string): Promise<{ message: string; documents_deleted: number; storage_cleanup_pending: boolean }> {
    return this.request(`/subjects?name=${encodeURIComponent(name)}`, { method: 'DELETE' });
  }

  async openPdf(documentId: number, page?: number): Promise<void> {
    // Reserve a tab during the click so browsers do not block the async PDF open.
    const viewer = window.open('about:blank', '_blank');
    if (!viewer) throw new Error('Allow a new tab to view this PDF.');
    viewer.opener = null;
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 120000);
    try {
      const headers = new Headers();
      if (this.token) headers.set('Authorization', `Bearer ${this.token}`);
      const response = await fetch(`${API_BASE}/documents/${documentId}/download`, { headers, signal: controller.signal, cache: 'no-store' });
      if (!response.ok) throw new Error('Could not open this PDF. Sign in to the account that owns it.');
      const blob = await response.blob();
      if (!blob.type.startsWith('application/pdf')) throw new Error('The server did not return a PDF.');
      const url = URL.createObjectURL(blob);
      viewer.location.replace(`${url}${page ? `#page=${page}` : ''}`);
      setTimeout(() => URL.revokeObjectURL(url), 300000);
    } catch (error) {
      viewer.close();
      throw error;
    } finally {
      clearTimeout(timeout);
    }
  }

  // Auth
  async register(data: { email: string; username: string; password: string }): Promise<{ access_token: string; user: User }> {
    const res = await this.request<{ access_token: string; user: User }>('/auth/register', {
      method: 'POST',
      body: JSON.stringify(data),
    });
    this.setToken(res.access_token);
    return res;
  }

  async login(data: { email: string; password: string }): Promise<{ access_token: string; user: User }> {
    const res = await this.request<{ access_token: string; user: User }>('/auth/login', {
      method: 'POST',
      body: JSON.stringify(data),
    });
    this.setToken(res.access_token);
    return res;
  }

  async getCurrentUser(): Promise<User> {
    return this.request<User>('/auth/me');
  }

  // Preferences
  async getPreferences(): Promise<UserPreference> {
    return this.request<UserPreference>('/users/preferences');
  }

  async updatePreferences(prefs: Partial<UserPreference>): Promise<UserPreference> {
    return this.request<UserPreference>('/users/preferences', {
      method: 'PUT',
      body: JSON.stringify(prefs),
    });
  }

  // Documents
  async listDocuments(subject?: string, signal?: AbortSignal): Promise<Document[]> {
    const query = subject && subject !== 'All' ? `?subject=${encodeURIComponent(subject)}` : '';
    return this.request<Document[]>(`/documents${query}`, { signal });
  }

  async getDocument(id: number): Promise<Document> {
    return this.request<Document>(`/documents/${id}`);
  }

  async uploadDocument(file: File, title: string, subject: string, autoProcess = true): Promise<DocumentUploadResponse> {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('title', title);
    formData.append('subject', subject);
    formData.append('auto_process', String(autoProcess));

    return this.request<DocumentUploadResponse>('/documents/upload', {
      method: 'POST',
      body: formData,
    }, UPLOAD_TIMEOUT_MS);
  }

  async processDocument(documentId: number): Promise<DocumentProcessResponse> {
    return this.request<DocumentProcessResponse>(`/documents/${documentId}/process`, {
      method: 'POST',
    });
  }

  async deleteDocument(documentId: number): Promise<{ message: string; storage_cleanup_pending?: boolean }> {
    return this.request<{ message: string }>(`/documents/${documentId}`, {
      method: 'DELETE',
    });
  }

  // Conversations
  async listConversations(): Promise<Conversation[]> {
    return this.request<Conversation[]>('/conversations');
  }

  async createConversation(data: { title?: string; subject?: string }): Promise<Conversation> {
    return this.request<Conversation>('/conversations', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async getConversation(id: number, signal?: AbortSignal): Promise<Conversation & { messages: Message[] }> {
    return this.request<Conversation & { messages: Message[] }>(`/conversations/${id}`, { signal });
  }

  async deleteConversation(id: number): Promise<{ message: string }> {
    return this.request<{ message: string }>(`/conversations/${id}`, {
      method: 'DELETE',
    });
  }

  async sendMessage(
    conversationId: number,
    query: {
      question: string;
      subject?: string;
      explanation_level?: string;
      answer_style?: string;
      include_examples?: boolean;
    },
    signal?: AbortSignal
  ): Promise<QueryResponse> {
    return this.request<QueryResponse>(`/conversations/${conversationId}/messages`, {
      method: 'POST',
      body: JSON.stringify(query),
      signal,
    }, ANSWER_TIMEOUT_MS);
  }

  // Direct Query
  async directQuery(query: {
    question: string;
    subject?: string;
    explanation_level?: string;
    answer_style?: string;
    include_examples?: boolean;
  }, signal?: AbortSignal): Promise<QueryResponse> {
    return this.request<QueryResponse>('/query', {
      method: 'POST',
      body: JSON.stringify(query),
      signal,
    }, ANSWER_TIMEOUT_MS);
  }
}

export const api = new ApiService();
