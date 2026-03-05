from pydantic import BaseModel, Field
from typing import List, Optional


class BoundingBox(BaseModel):
    x0: float
    y0: float
    x1: float
    y1: float


class TextChunk(BaseModel):
    text: str
    page_number: int
    char_offset: int
    bounding_box: BoundingBox


class RelatedTextRequest(BaseModel):
    pdf_id: str = Field(..., min_length=1, description="PDF document identifier")
    query: str = Field(..., min_length=1, max_length=1000, description="Text to find related passages for")
    top_k: int = Field(default=5, ge=1, le=20, description="Number of results to return")


class RelatedMatch(BaseModel):
    text: str
    snippet: str
    page_number: int
    confidence: float = Field(..., ge=0.0, le=1.0)
    bounding_box: BoundingBox
    char_offset: int
    rationale: str


class RelatedTextResponse(BaseModel):
    results: List[RelatedMatch]
    query: str
    total_matches: int


class UploadResponse(BaseModel):
    pdf_id: str
    filename: str
    page_count: int
    status: str


class ErrorResponse(BaseModel):
    error: str
    detail: Optional[str] = None
