# PDF Semantic Search Application

**Date**: 2026-03-04

## TL;DR
A full-stack PDF viewer with AI-powered semantic search. Users can highlight text in PDFs and find semantically related passages using embedding-based similarity search.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        Frontend (React)                         │
│  ┌─────────────┐  ┌─────────────────┐  ┌─────────────────────┐ │
│  │  PDF Viewer │  │  Highlight Mgmt │  │  Related Results    │ │
│  │  (react-pdf)│  │  (Side Panel)   │  │  Panel              │ │
│  └─────────────┘  └─────────────────┘  └─────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Backend (FastAPI)                          │
│  ┌─────────────┐  ┌─────────────────┐  ┌─────────────────────┐ │
│  │ PDF Parser  │  │  Embeddings     │  │  Vector Search      │ │
│  │ (PyMuPDF)   │  │  (sentence-     │  │  (FAISS)            │ │
│  │             │  │   transformers) │  │                     │ │
│  └─────────────┘  └─────────────────┘  └─────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

## AI/Embedding Strategy

### Chosen Approach: Embedding-based Search with Local Models

**Strategy**: Hybrid approach combining:
1. **Sentence Transformers** (`all-MiniLM-L6-v2`) for generating embeddings
2. **FAISS** for efficient similarity search
3. **Chunking** with overlap for better context preservation

**Why This Approach**:
- **Privacy**: No external API calls - all processing is local
- **Speed**: Pre-computed embeddings enable sub-second search
- **Cost**: No per-query costs (no paid API dependencies)
- **Quality**: `all-MiniLM-L6-v2` provides excellent semantic understanding

**Trade-offs**:
- Requires ~100MB model download on first run
- Less powerful than GPT-4 embeddings, but sufficient for document search
- Memory usage scales with PDF size

**Alternative Considered**:
- OpenAI embeddings: Better quality but requires API key and has latency/cost
- BM25 only: Faster but misses semantic relationships

### Chunking Strategy
- **Chunk size**: 200 characters with 50 character overlap
- **Rationale**: Small chunks for precise matching while overlap preserves context
- Each chunk stores: text, page number, character offset, bounding box coordinates

## Project Structure

```
pdf-semantic-search/
├── frontend/                 # React application
│   ├── src/
│   │   ├── components/
│   │   │   ├── PDFViewer.jsx
│   │   │   ├── HighlightPanel.jsx
│   │   │   ├── RelatedResults.jsx
│   │   │   └── HighlightOverlay.jsx
│   │   ├── App.jsx
│   │   └── index.jsx
│   ├── package.json
│   └── vite.config.js
├── backend/                  # FastAPI application
│   ├── app/
│   │   ├── main.py
│   │   ├── pdf_processor.py
│   │   ├── embeddings.py
│   │   └── models.py
│   ├── requirements.txt
│   └── uploads/              # PDF storage
└── README.md
```

## API Schema

### POST /api/upload-pdf
Upload a PDF for processing.

**Request**: `multipart/form-data` with `file` field

**Response**:
```json
{
  "pdf_id": "abc123",
  "filename": "document.pdf",
  "page_count": 42,
  "status": "processed"
}
```

### POST /api/related-text
Find semantically related text passages.

**Request**:
```json
{
  "pdf_id": "abc123",
  "query": "machine learning algorithms",
  "top_k": 5
}
```

**Response**:
```json
{
  "results": [
    {
      "text": "...neural networks are a subset of machine learning...",
      "snippet": "Neural networks are a subset of machine learning that mimics the human brain...",
      "page_number": 7,
      "confidence": 0.89,
      "bounding_box": {
        "x0": 72.0,
        "y0": 450.5,
        "x1": 540.0,
        "y1": 480.2
      },
      "char_offset": 3421,
      "rationale": "High semantic similarity: both discuss ML paradigms"
    }
  ],
  "query": "machine learning algorithms",
  "total_matches": 5
}
```

## Setup Instructions

```bash 
Create account in QDRANT to get QDRANT_URL and QDRANT_API_KEY
```

### Backend
```bash
cd services/backend
cp .env.example .env
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

### Frontend
```bash
cd services/frontend
npm install
npm run dev
```

## Performance
- PDF processing: ~2-3 seconds for 50 pages
- Semantic search: <500ms after initial embedding
- Embeddings are cached per PDF to avoid recomputation

## Dependencies

### Backend
- FastAPI + Uvicorn
- PyMuPDF (fitz) - PDF parsing with position data
- sentence-transformers - Local embedding model
- faiss-cpu - Vector similarity search
- python-multipart - File uploads

### Frontend
- React 18
- react-pdf - PDF rendering
- Vite - Build tool
- CSS for styling (no heavy framework)
