import numpy as np
import faiss
from sentence_transformers import SentenceTransformer
from typing import List, Dict, Tuple, Optional
from .models import TextChunk, RelatedMatch, BoundingBox
from .pdf_processor import get_snippet
from qdrant_client import QdrantClient, models
import logging
import os
from load_dotenv import load_dotenv

load_dotenv()


QDRANT_URL = os.getenv("QDRANT_URL", "")
QRANT_API_KEY = os.getenv("QDRANT_API_KEY","")
logging.basicConfig(
    level=logging.DEBUG,  
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)

class PDFIndex:
    def __init__(self, pdf_id: str, chunks: List[TextChunk]):
        self.pdf_id = pdf_id
        self.chunks = chunks
        self.embeddings: Optional[np.ndarray] = None
        self.index: Optional[faiss.IndexFlatIP] = None
        self.qdrant_client = QdrantClient(url=QDRANT_URL, api_key=QRANT_API_KEY)
    
    
    def build_index(self,model:SentenceTransformer) -> None:
        logger.info("Building index for PDF")
        if not self.chunks:
            return
        
        # model = get_model()
        texts = [chunk.text for chunk in self.chunks]
        self.embeddings = model.encode(texts, convert_to_numpy=True, normalize_embeddings=True)
        
        collections_name = [collection.name for collection in self.qdrant_client.get_collections().collections]
        if "temp" in collections_name:
            logger.info("delete collection temp if exists")
            self.qdrant_client.delete_collection(collection_name = "temp")
        
        logger.info("create collection temp")
        self.qdrant_client.create_collection(
            collection_name = "temp",
            vectors_config = models.VectorParams(
                size = model.get_sentence_embedding_dimension(), # dimensions = 384
                distance = models.Distance.COSINE),
        )

        logger.info("Upload points to qdrant")
        #create points and upload to qdrant
        self.qdrant_client.upload_points(
            collection_name = "temp",
            points = [
                models.PointStruct(
                    id=idx,
                    vector = model.encode(chunk.text).tolist(),
                    payload = {"passage_text":chunk.text,
                               "page_number":chunk.page_number,
                               "char_offset":chunk.char_offset,
                               "bounding_box":chunk.bounding_box}
                    
                )
                for idx, chunk in enumerate(self.chunks)
            ]
        )

    
    def search(
        self, 
        query_embedding: np.ndarray, 
        top_k: int = 5
    ) -> List[Tuple[int, float]]:
        logger.info("Search top_k documents from qdrant")
        try:
            top_relevant = self.qdrant_client.query_points(
                collection_name = "temp",
                query = query_embedding.tolist(),
                limit = top_k,
            ).points
        except Exception as e:
            logger.error(f"Failed to query in qdrant:{e}")
            
        
        results = [(point.id, float(point.score),point.payload) for point in top_relevant]
        return results



class RAGEngine:
    def __init__(self):
        pass


    def search_related_text(
        self,
        pdf_id: str, 
        query: str, 
        model:SentenceTransformer,
        top_k: int = 5,
       
    ) -> List[RelatedMatch]:
        logger.info("Retrieval documents")
        pdf_index = PDFIndex(pdf_id, [])
        
        logger.info(f"Search related text for query: {query}")
        query_embedding = model.encode(query, convert_to_numpy=True, normalize_embeddings=True)
        
        search_results = pdf_index.search(query_embedding, top_k)
        
        matches = []
        for result in search_results:
            idx, score,payload  = result
    
                
            confidence = score
            # confidence = (score + 1) / 2
            # confidence = max(0.0, min(1.0, confidence))
            
            rationale = self.generate_rationale(query, payload['passage_text'], confidence)
            
            matches.append(RelatedMatch(
                text=payload['passage_text'],
                snippet=get_snippet(payload['passage_text']),
                page_number=payload['page_number'],
                confidence=round(score, 3),
                bounding_box=payload['bounding_box'],
                char_offset=payload['char_offset'],
                rationale=rationale
            ))
        
        return matches


    def generate_rationale(self,query: str, matched_text: str, confidence: float) -> str:
        logger.info("generate rationale..")
        query_words = set(query.lower().split())
        text_words = set(matched_text.lower().split())
        common_words = query_words & text_words
        
        if confidence >= 0.8:
            strength = "High"
            explanation = "Strong semantic alignment"
        elif confidence >= 0.6:
            strength = "Moderate"
            explanation = "Related concepts found"
        else:
            strength = "Weak"
            explanation = "Partial topic overlap"
        
        if common_words:
            keywords = ", ".join(list(common_words)[:3])
            return f"{strength} semantic similarity ({confidence:.0%}): {explanation}. Shared terms: {keywords}"
        else:
            return f"{strength} semantic similarity ({confidence:.0%}): {explanation}"
