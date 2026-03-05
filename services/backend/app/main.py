import os
import shutil
from pathlib import Path
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from .models import (
    RelatedTextRequest, 
    RelatedTextResponse, 
    UploadResponse, 
    ErrorResponse
)
from sentence_transformers import SentenceTransformer
from contextlib import asynccontextmanager

from .pdf_processor import extract_text_with_positions, generate_pdf_id
from .embeddings import PDFIndex, RAGEngine
import logging
from load_dotenv import load_dotenv
import os 

logging.basicConfig(
    level=logging.DEBUG,   
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)

logger = logging.getLogger(__name__)

load_dotenv()
UPLOAD_DIR = Path(__file__).parent.parent / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

MODEL_NAME = os.getenv("MODEL_EMBEDDING", "")
_pdf_metadata: dict = {}
_pdf_stores: dict = {}



@asynccontextmanager
async def lifespan(app: FastAPI):
    # STARTUP
    logger.info("App is starting...")
    app.state.model = SentenceTransformer(MODEL_NAME)  #load embedding model
    yield
    # SHUTDOWN
    logger.info("App is shutting down...")

app = FastAPI(
    lifespan=lifespan,    
    title="PDF Semantic Search API",
    description="AI-powered semantic search within PDF documents",
    version="1.0.0")


app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    return {"message": "PDF Semantic Search API", "status": "running"}


@app.post("/api/upload-pdf", response_model=UploadResponse)
async def upload_pdf(file: UploadFile = File(...)):
   
    #check file upload
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")
    
    #check file type
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="File must be a PDF")
    
    logger.info("Process file upload...")
    try:
        #read file content
        content = await file.read()
        
        if len(content) == 0:
            raise HTTPException(status_code=400, detail="Empty file")
        
        #limit file size to 50MB
        if len(content) > 50 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="File too large (max 50MB)")
        
        pdf_id = generate_pdf_id(file.filename, content)
        
        pdf_path = UPLOAD_DIR / f"{pdf_id}.pdf"
        with open(pdf_path, "wb") as f:
            f.write(content)
        
        chunks, page_count = extract_text_with_positions(str(pdf_path))
        
        if not chunks:
            raise HTTPException(
                status_code=400, 
                detail="Could not extract text from PDF. The file may be image-based or corrupted."
            )
        
        page_index = PDFIndex(pdf_id, chunks)
        logger.info("Build index and upload...")
        #build index and store in qdrant
        page_index.build_index(app.state.model)
        #store page_index
        _pdf_stores[pdf_id] = chunks

        _pdf_metadata[pdf_id] = {
            "filename": file.filename,
            "page_count": page_count,
            "path": str(pdf_path)
        }
        
        return UploadResponse(
            pdf_id=pdf_id,
            filename=file.filename,
            page_count=page_count,
            status="processed"
        )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Processing error: {str(e)}")


@app.post("/api/related-text", response_model=RelatedTextResponse)
async def find_related_text(request: RelatedTextRequest):
    if not request.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")
    
    #page_index = PDFIndex(request.pdf_id, [])
    rag_engine = RAGEngine()
    pdf_index = _pdf_metadata.get(request.pdf_id)
    if pdf_index is None:
        raise HTTPException(
            status_code=404, 
            detail=f"PDF with id '{request.pdf_id}' not found. Please upload the PDF first."
        )
    
    logger.info("Start retrieval related-text")

    try:
        matches = rag_engine.search_related_text(
            pdf_id = request.pdf_id, 
            query = request.query.strip(), 
            top_k = request.top_k,
            model = app.state.model
        )
        
        return RelatedTextResponse(
            results=matches,
            query=request.query,
            total_matches=len(matches)
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search error: {str(e)}")


@app.get("/api/pdf/{pdf_id}")
async def get_pdf(pdf_id: str):
    if pdf_id not in _pdf_metadata:
        raise HTTPException(status_code=404, detail="PDF not found")
    
    pdf_path = _pdf_metadata[pdf_id]["path"]
    if not os.path.exists(pdf_path):
        raise HTTPException(status_code=404, detail="PDF file not found on disk")
    
    return FileResponse(
        pdf_path, 
        media_type="application/pdf",
        filename=_pdf_metadata[pdf_id]["filename"]
    )


@app.get("/api/pdf/{pdf_id}/info")
async def get_pdf_info(pdf_id: str):
    logger.info("get pdf information...")
    if pdf_id not in _pdf_metadata:
        raise HTTPException(status_code=404, detail="PDF not found")
    
    return {
        "pdf_id": pdf_id,
        **_pdf_metadata[pdf_id]
    }


@app.delete("/api/pdf/{pdf_id}")
async def delete_pdf(pdf_id: str):
    logger.info("Delete pdf")
    if pdf_id not in _pdf_metadata:
        raise HTTPException(status_code=404, detail="PDF not found")
    
    try:
        pdf_path = _pdf_metadata[pdf_id]["path"]
        if os.path.exists(pdf_path):
            os.remove(pdf_path)
        
        # from .embeddings import remove_pdf_index
        # remove_pdf_index(pdf_id)
        
        del _pdf_metadata[pdf_id]
        
        return {"message": "PDF deleted successfully"}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Delete error: {str(e)}")
