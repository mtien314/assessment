import fitz
import hashlib
from pathlib import Path
from typing import List, Dict, Tuple
from .models import TextChunk, BoundingBox


CHUNK_SIZE = 200
CHUNK_OVERLAP = 50


def generate_pdf_id(filename: str, content: bytes) -> str:
    hash_input = f"{filename}-{len(content)}-{hashlib.md5(content).hexdigest()[:8]}"
    return hashlib.sha256(hash_input.encode()).hexdigest()[:12]


def extract_text_with_positions(pdf_path: str) -> Tuple[List[TextChunk], int]:
    doc = fitz.open(pdf_path)
    chunks: List[TextChunk] = []
    page_count = len(doc)
    
    for page_num in range(page_count):
        page = doc[page_num]
        blocks = page.get_text("dict")["blocks"]
        
        page_text = ""
        char_positions: List[Dict] = []
        
        for block in blocks:
            if block.get("type") == 0:
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        text = span.get("text", "")
                        bbox = span.get("bbox", [0, 0, 0, 0])
                        
                        start_offset = len(page_text)
                        page_text += text
                        
                        for i, char in enumerate(text):
                            char_ratio = i / max(len(text), 1)
                            char_x = bbox[0] + (bbox[2] - bbox[0]) * char_ratio
                            char_positions.append({
                                "char": char,
                                "offset": start_offset + i,
                                "bbox": BoundingBox(
                                    x0=char_x,
                                    y0=bbox[1],
                                    x1=char_x + (bbox[2] - bbox[0]) / max(len(text), 1),
                                    y1=bbox[3]
                                )
                            })
                    page_text += " "
                    char_positions.append({
                        "char": " ",
                        "offset": len(page_text) - 1,
                        "bbox": BoundingBox(x0=0, y0=0, x1=0, y1=0)
                    })
        
        page_chunks = create_chunks_from_page(
            page_text, 
            char_positions, 
            page_num + 1
        )
        chunks.extend(page_chunks)
    
    doc.close()
    return chunks, page_count


def create_chunks_from_page(
    text: str, 
    char_positions: List[Dict], 
    page_number: int
) -> List[TextChunk]:
    chunks = []
    text = text.strip()
    
    if not text:
        return chunks
    
    start = 0
    while start < len(text):
        end = min(start + CHUNK_SIZE, len(text))
        
        if end < len(text):
            space_idx = text.rfind(" ", start, end)
            if space_idx > start + CHUNK_SIZE // 2:
                end = space_idx
        
        chunk_text = text[start:end].strip()
        
        if chunk_text:
            bbox = calculate_chunk_bbox(char_positions, start, end)
            
            chunks.append(TextChunk(
                text=chunk_text,
                page_number=page_number,
                char_offset=start,
                bounding_box=bbox
            ))
        
        start = end - CHUNK_OVERLAP if end < len(text) else end
        if start < 0:
            start = 0
    
    return chunks


def calculate_chunk_bbox(
    char_positions: List[Dict], 
    start: int, 
    end: int
) -> BoundingBox:
    relevant_positions = [
        p for p in char_positions 
        if start <= p["offset"] < end and p["bbox"].x0 > 0
    ]
    
    if not relevant_positions:
        return BoundingBox(x0=0, y0=0, x1=0, y1=0)
    
    x0 = min(p["bbox"].x0 for p in relevant_positions)
    y0 = min(p["bbox"].y0 for p in relevant_positions)
    x1 = max(p["bbox"].x1 for p in relevant_positions)
    y1 = max(p["bbox"].y1 for p in relevant_positions)
    
    return BoundingBox(x0=x0, y0=y0, x1=x1, y1=y1)


def get_snippet(text: str, max_length: int = 150) -> str:
    if len(text) <= max_length:
        return text
    
    truncated = text[:max_length]
    last_space = truncated.rfind(" ")
    if last_space > max_length // 2:
        truncated = truncated[:last_space]
    
    return truncated + "..."
