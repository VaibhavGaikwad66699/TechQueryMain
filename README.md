# TechQuery — AI-Based Technical Knowledge Assistant

TechQuery is a local full-stack AI technical knowledge assistant built with **React**, **FastAPI**, **SQLite**, and **Google Gemini RAG (Retrieval-Augmented Generation)**. Core local workflows have been reviewed; final acceptance checks remain. See the verified project status below.

Every account includes the same four **C, C++, Java and Python Notes for Professionals** books. Users can add personal subjects (for example Biology or Operating Systems), upload reference PDFs, and ask questions using their own explanation level, answer style and example preferences. Custom subjects and uploads belong only to their owner. Guests can use the four default books.

**All my subjects** searches the four defaults plus the signed-in user's own books. A selected subject searches only that subject within this account's visible library. Another user's PDFs, citations, subject names, conversations and preferences are excluded. Private PDF downloads require the owner's authorization; the frontend opens them through an authenticated request. Default books are shared once rather than copied for each new account, and cannot be deleted through the website.

Personal subjects can be removed from **Knowledge Base → My personal subjects → Delete subject** after confirmation, which removes that subject's source PDFs and search data and resets its preferred-subject setting. A PDF's trash button deletes only that book. The four defaults are protected; existing conversations remain until separately deleted from history.

The source PDFs are in `source_book/C`, `source_book/C++`, `source_book/JAVA`, and `source_book/PYTHON`. All four have searchable text and recorded Google approval. Compatible embeddings are **3,680/9,320**, with **5,640 remaining** after the 22 October quota stop. The default library contains exactly these four books. Browser uploads disclose Google processing; operator imports still respect their local-only flags. See [project status](docs/PROJECT_STATUS.md), [the library contract](docs/PRIVATE_LIBRARY.md), and [the scope contract](docs/PROGRAMMING_SCOPE.md).

Production configuration, Docker/Compose files, backup/restore tools and a sanitized four-book dataset are now prepared locally. Read the [production runbook](docs/PRODUCTION_DEPLOYMENT.md) before using them. Docker build/HTTPS/cloud validation remain pending; no AWS resources have been provisioned.

---

For verified results and remaining release work, read [Project status](docs/PROJECT_STATUS.md). For current startup, indexing, evaluation and recovery commands, read [Day 1 runbook](docs/DAY1_RUNBOOK.md). Feature descriptions below are not a production-readiness guarantee.

## Architecture Overview

```
+-------------------------------------------------------------------------+
|                           TechQuery Frontend                            |
|             (React 18 + TypeScript + Vite + Tailwind CSS)               |
|                                                                         |
|  - Calm Study Workspace                - Knowledge Base Manager        |
|  - Real-Time Q&A Chat Interface         - User Preferences Modal        |
|  - Multi-Thread Conversation History    - Source Citation Cards         |
+------------------------------------+------------------------------------+
                                     |  HTTP REST / Bearer JWT
                                     v
+-------------------------------------------------------------------------+
|                           TechQuery Backend                             |
|                    (Python 3.13 + FastAPI + SQLite)                     |
|                                                                         |
|  - /api/v1/auth          -> User Registration & JWT Authentication      |
|  - /api/v1/users         -> User Preferences (Level, Style, Examples)   |
|  - /api/v1/documents     -> PDF Upload, Page Chunking & Storage         |
|  - /api/v1/conversations -> Conversation Threads & Message History      |
|  - /api/v1/query         -> RAG Query Engine (Semantic + Fallback)      |
|  - /api/v1/health        -> Health Status & Subject Discovery           |
+-------------------+--------------------------------+--------------------+
                    |                                |
                    v                                v
+------------------------------------+ +------------------------------------+
|         Local Storage Layer        | |        AI & Embeddings (RAG)       |
|                                    | |                                    |
| - SQLite DB: `data/techquery.db`   | | - Embeddings: `gemini-embedding-001` |
|   * Users, Preferences, Documents  | | - LLM: Google Gemini 3.5 Flash-Lite     |
|   * DocumentChunks (with vectors)  | | - Cosine Similarity via NumPy      |
| - Local Files: `data/documents/`   | | - Grounded Context Construction    |
+------------------------------------+ +------------------------------------+
```

---

## Key Features

1. **Retrieval-Augmented Generation (RAG)**:
   - Extracts page-by-page text from uploaded PDFs (`pypdf`).
   - Splits text into manageable, overlapping semantic chunks preserving exact page numbers and document IDs.
   - Computes high-dimensional vector embeddings with Google Gemini (`gemini-embedding-001`).
   - Retrieves the top relevant passages using NumPy vector cosine similarity.
   - Formulates grounded prompts for Gemini with strict instructions against fabricating citations or hallucinations.
   - Graceful fallback: If no Gemini key is supplied, a smart lexical keyword retrieval engine ensures search and local testing still work.

2. **Personalized User Preferences**:
   - **Explanation Level**: Beginner, Intermediate, Advanced
   - **Answer Style**: Concise, Detailed
   - **Examples**: Include code snippets vs. Conceptual only
   - Applied dynamically to Gemini prompts.

3. **Multi-Threaded Conversations & History**:
   - Create, rename, delete, and switch between conversations.
   - Retains conversation history and inspectable source citations for every answer.

4. **Document Knowledge Base Management**:
   - Upload PDF textbooks directly from the browser.
   - Choose a default subject or create a personal subject with **Add subject**. Queries, uploads, conversations and preferences validate subjects against the current account.
   - View processing status, page counts, chunk counts, and error messages.
   - Deleting a document safely cascades and deletes all associated indexed chunks.

5. **Local-First & Cloud-Ready Modular Design**:
   - **Zero Cloud Costs / Zero Paid Services**: Fully runs on your laptop with zero AWS or cloud dependencies at this stage.
   - Abstract `StorageService` interface: Easily swapped for AWS S3 in future phases without rewriting application logic.
   - SQLAlchemy ORM: Database models are completely portable to PostgreSQL + `pgvector`.

---

## Prerequisites

- **Node.js**: v18+ (tested on v24.13.1)
- **Python**: 3.10+ (tested on Python 3.13)
- **Google Gemini API Key**: Free key from [Google AI Studio](https://aistudio.google.com/app/apikey).

---

## Installation & Setup

### 1. Clone or Open Workspace
Navigate to your project root:
```powershell
cd d:\Project
```

### 2. Configure Environment Variables
Copy the example environment file:
```powershell
cp .env.example backend/.env
```
Open `backend/.env` and paste your free Google Gemini API key:
```env
GEMINI_API_KEY=AIzaSy...your_gemini_key_here
```
*(Note: If you leave it blank, TechQuery will start normally and use lexical search with a friendly setup notice).*

### 3. Backend Setup (Python)
TechQuery uses an isolated Python virtual environment:

```powershell
# In d:\Project\backend
cd d:\Project\backend

# Activate virtual environment
.\.venv\Scripts\Activate.ps1

# Install required dependencies
pip install -r requirements.lock.txt
```

### 4. Frontend Setup (React + Vite)
```powershell
# In d:\Project\frontend
cd d:\Project\frontend

# Install dependencies (use npm.cmd in Windows PowerShell)
npm.cmd install
```

---

## Running the Application

### Method 1: One-Click Windows Batch Launcher (Recommended)
Simply double-click:
```powershell
run_techquery.bat
```
This launcher checks your environment, verifies your Gemini API key status, spins up both the FastAPI backend and Vite frontend, displays a live terminal status dashboard, and automatically opens **http://localhost:5173** in your default browser.

To stop all servers at any time, run:
```powershell
stop_techquery.bat
```

---

### Method 2: Manual Terminal Startup

#### Terminal 1 — Backend Server
```powershell
cd d:\Project\backend
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```
- API Docs (Swagger UI): **http://127.0.0.1:8000/docs**
- Health Check: **http://127.0.0.1:8000/api/v1/health**
- Readiness (no provider call): **http://127.0.0.1:8000/api/v1/ready**

PDF extraction/indexing runs in background jobs in one API process. Upload returns 201 and processing returns 202 acceptance; the UI polls document status for completion. Incomplete embeddings yield `partial` with searchable text. Default upload size is 50 MiB. See the [frontend review](docs/FRONTEND_REVIEW.md) for tested flows, responsive sizes and acceptance limits. S3 and AWS work are deferred until local acceptance.

### Option B: Run Frontend Development Server
In PowerShell Terminal 2:
```powershell
cd d:\Project\frontend
npm.cmd run dev
```
- TechQuery Web Interface: **http://localhost:5173**

---

## How to Test the RAG Workflow

1. Open **http://localhost:5173** in your browser.
2. Click **Knowledge Base** in the top navbar.
3. Upload an authorized C, C++, Java, or Python PDF.
4. Choose its subject (use **Add subject** first for a new one) and click **Upload & Process Book**.
5. Wait for searchable text (`partial`) or complete semantic indexing (`ready`), then navigate to **Chat & QA**. A large book can remain partial because processing is bounded or provider quota is exhausted; extracted chunk counts are not embedding counts.
6. Ask a question such as:
   - *"What is an interface in Java?"*
   - *"What is the difference between lists and tuples in Python?"* (requires a processed Python book)
7. Open **Preferences** to toggle between **Beginner / Advanced** or request code examples.
8. Inspect the **Sources** card below the AI answer to see exact page numbers and excerpts from the textbook!

---

## Running Automated Backend Tests

TechQuery includes an automated test suite verifying auth, document lifecycle, RAG retrieval, and conversation history:

```powershell
cd d:\Project\backend
.\.venv\Scripts\python.exe -m pytest -v
```

Frontend client regressions and production build (no additional test packages required):

```powershell
cd d:\Project\frontend
npm.cmd test
npm.cmd run build
```

Current results: 54 backend tests, 6 frontend client tests, and the production build pass. Browser coverage and remaining release checks are recorded in the project status.

---

## Project Structure

```
d:\Project\
├── backend/
│   ├── app/
│   │   ├── api/            # API endpoints (auth, conversations, documents, health, rag, users)
│   │   ├── core/           # Security (JWT, bcrypt) and application settings
│   │   ├── database/       # SQLAlchemy engine and session dependency
│   │   ├── models/         # User, Document, DocumentChunk, Conversation, Message
│   │   ├── schemas/        # Pydantic v2 schemas and validation
│   │   ├── services/       # PDFService, EmbeddingService, RAGService, StorageService
│   │   └── main.py         # FastAPI application entrypoint with CORS & routes
│   ├── tests/              # Pytest test suite (54 automated unit & integration tests)
│   ├── requirements.txt    # Python dependencies
│   └── .env                # Local backend environment variables (gitignored)
├── frontend/
│   ├── src/
│   │   ├── components/     # ChatInterface, DocumentManager, Sidebar, Navbar, Modals
│   │   ├── context/        # AuthContext & learning preferences state
│   │   ├── services/       # REST API service client with token interceptor
│   │   ├── types/          # TypeScript interface definitions
│   │   ├── App.tsx         # Main layout and tab router
│   │   └── index.css       # Design system and custom styles
│   ├── package.json
│   ├── tsconfig.json
│   └── vite.config.ts      # Vite dev server with proxy to backend
├── data/
│   ├── documents/          # Uploaded PDF textbooks (gitignored)
│   └── techquery.db        # SQLite database file (gitignored)
├── .env.example            # Template for environment variables
├── .gitignore
└── README.md
```

---

## Troubleshooting

- **PowerShell Script Execution Policy (`npm.ps1 cannot be loaded`)**:
  On Windows systems where script execution is restricted, run `npm.cmd` instead of `npm` (e.g. `npm.cmd run dev` or `npm.cmd install`).
- **Gemini Quota or Invalid API Key**:
  If the Gemini API key is missing or invalid, TechQuery automatically falls back to local lexical retrieval and displays a helpful banner instead of crashing.
