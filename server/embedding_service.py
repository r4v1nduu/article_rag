from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from sentence_transformers import SentenceTransformer
import uvicorn
import logging
import torch
from typing import List
import time

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Document Embedding Service", version="1.0.0")

# Request/Response models
class EmbeddingRequest(BaseModel):
    text: str

class BatchEmbeddingRequest(BaseModel):
    texts: List[str]

class EmbeddingResponse(BaseModel):
    embedding: List[float]
    processing_time: float

class BatchEmbeddingResponse(BaseModel):
    embeddings: List[List[float]]
    processing_time: float
    count: int

class HealthResponse(BaseModel):
    status: str
    model: str
    vector_size: int
    device: str
    total_requests: int

# Global variables
model = None
device = None
request_count = 0

def load_model():
    """Load the sentence transformer model"""
    global model, device
    try:
        logger.info("🔄 Loading SentenceTransformer model...")
        
        # Check for GPU availability
        device = "cuda" if torch.cuda.is_available() else "cpu"
        logger.info(f"🔧 Using device: {device}")
        
        # Load model
        model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2', device=device)
        
        logger.info("✅ Model loaded successfully")
        logger.info(f"📏 Vector dimension: {model.get_sentence_embedding_dimension()}")
        
        return model
    except Exception as e:
        logger.error(f"❌ Failed to load model: {e}")
        raise

@app.on_event("startup")
async def startup_event():
    """Initialize the model when the service starts"""
    load_model()
    logger.info("🚀 Embedding service ready!")

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    global request_count
    
    if model is None:
        raise HTTPException(status_code=503, detail="Model not loaded")
    
    return HealthResponse(
        status="healthy",
        model="sentence-transformers/all-MiniLM-L6-v2",
        vector_size=384,
        device=str(device),
        total_requests=request_count
    )

@app.post("/encode", response_model=EmbeddingResponse)
async def encode_text(request: EmbeddingRequest):
    """Generate embedding for a single text"""
    global request_count
    
    if model is None:
        raise HTTPException(status_code=503, detail="Model not loaded")
    
    try:
        if not request.text.strip():
            raise HTTPException(status_code=400, detail="Text cannot be empty")
        
        start_time = time.time()
        
        # Generate embedding
        embedding = model.encode(request.text, convert_to_tensor=False)
        
        # Convert to Python list
        embedding_list = embedding.tolist()
        
        processing_time = time.time() - start_time
        request_count += 1
        
        logger.info(f"✅ Generated embedding for text: {request.text[:100]}... (took {processing_time:.3f}s)")
        
        return EmbeddingResponse(
            embedding=embedding_list,
            processing_time=processing_time
        )
        
    except Exception as e:
        logger.error(f"❌ Error generating embedding: {e}")
        raise HTTPException(status_code=500, detail=f"Error generating embedding: {str(e)}")

@app.post("/encode_batch", response_model=BatchEmbeddingResponse)
async def encode_batch(request: BatchEmbeddingRequest):
    """Generate embeddings for multiple texts (more efficient for batches)"""
    global request_count
    
    if model is None:
        raise HTTPException(status_code=503, detail="Model not loaded")
    
    try:
        if not request.texts or len(request.texts) == 0:
            raise HTTPException(status_code=400, detail="Texts list cannot be empty")
        
        # Filter out empty texts but keep track of original indices
        valid_texts = []
        text_indices = []
        
        for i, text in enumerate(request.texts):
            if text and text.strip():
                valid_texts.append(text)
                text_indices.append(i)
        
        if not valid_texts:
            raise HTTPException(status_code=400, detail="All texts are empty")
        
        start_time = time.time()
        
        # Generate embeddings for all valid texts at once (much faster)
        embeddings = model.encode(valid_texts, convert_to_tensor=False, batch_size=32)
        
        # Convert to Python lists
        embeddings_list = [emb.tolist() for emb in embeddings]
        
        processing_time = time.time() - start_time
        request_count += len(valid_texts)
        
        logger.info(f"✅ Generated {len(embeddings_list)} embeddings in batch (took {processing_time:.3f}s, {processing_time/len(embeddings_list):.3f}s per embedding)")
        
        return BatchEmbeddingResponse(
            embeddings=embeddings_list,
            processing_time=processing_time,
            count=len(embeddings_list)
        )
        
    except Exception as e:
        logger.error(f"❌ Error generating batch embeddings: {e}")
        raise HTTPException(status_code=500, detail=f"Error generating embeddings: {str(e)}")

@app.get("/stats")
async def get_stats():
    """Get service statistics"""
    global request_count
    
    return {
        "total_requests": request_count,
        "model_loaded": model is not None,
        "device": str(device) if device else "unknown",
        "model_name": "sentence-transformers/all-MiniLM-L6-v2",
        "vector_dimension": 384
    }

@app.post("/test")
async def test_endpoint():
    """Quick test endpoint"""
    if model is None:
        raise HTTPException(status_code=503, detail="Model not loaded")
    
    test_text = "This is a test document for the embedding service."
    
    try:
        start_time = time.time()
        embedding = model.encode(test_text, convert_to_tensor=False)
        processing_time = time.time() - start_time
        
        return {
            "status": "success",
            "test_text": test_text,
            "vector_size": len(embedding),
            "processing_time": processing_time,
            "sample_values": embedding[:5].tolist()  # First 5 values
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Test failed: {str(e)}")

@app.get("/")
async def root():
    """Root endpoint with API documentation"""
    return {
        "service": "Document Embedding Service",
        "model": "sentence-transformers/all-MiniLM-L6-v2",
        "vector_size": 384,
        "endpoints": {
            "/health": "Health check and service stats",
            "/encode": "Generate single embedding (POST with {text: 'your text'})",
            "/encode_batch": "Generate multiple embeddings (POST with {texts: ['text1', 'text2']})",
            "/test": "Run a quick test",
            "/stats": "Get service statistics",
            "/docs": "Interactive API documentation"
        }
    }

# Error handlers
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    logger.error(f"❌ Unhandled error: {exc}")
    return {"error": "Internal server error", "detail": str(exc)}

if __name__ == "__main__":
    print("🚀 Starting Document Embedding Service...")
    print("📡 Service will be available at http://0.0.0.0:8080")
    print("📚 API docs at http://0.0.0.0:8080/docs")
    
    # Run the service
    uvicorn.run(
        app,
        host="0.0.0.0",  # Listen on all interfaces
        port=8080,
        log_level="info",
        access_log=True
    )