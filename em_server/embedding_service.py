from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from sentence_transformers import SentenceTransformer
from transformers import AutoTokenizer, AutoModel
import uvicorn
import logging
import torch
from typing import List
import time

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Document Embedding Service", 
    version="1.0.0"
)

# Request/Response models
class EmbeddingRequest(BaseModel):
    text: str

class BatchEmbeddingRequest(BaseModel):
    texts: List[str]

class EmbeddingResponse(BaseModel):
    embedding: List[float]
    processing_time: float

class HealthResponse(BaseModel):
    status: str
    model: str
    vector_size: int
    device: str
    total_requests: int

# Global variables
model = None
tokenizer = None
device = None
request_count = 0

# Load the sentence transformer model
def load_model():
    global model, tokenizer, device
    try:
        device = "cuda" if torch.cuda.is_available() else "cpu"
        logger.info(f"[INFO] Using device: {device}")

        # Load tokenizer and model
        tokenizer = AutoTokenizer.from_pretrained("intfloat/e5-large")
        model = AutoModel.from_pretrained("intfloat/e5-large").to(device)
        model.eval()

        logger.info("[INFO] E5-Large model loaded successfully")
        return model
    except Exception as e:
        logger.error(f"[ERROR] Failed to load model: {e}")
        raise

# Initialize the model when the service starts
@app.on_event("startup")
async def startup_event():

    load_model()
    logger.info("[INFO] Embedding service ready!")

# Health check endpoint
@app.get("/health", response_model=HealthResponse)
async def health_check():

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

# Generate embedding for a single text
@app.post("/encode", response_model=EmbeddingResponse)
async def encode_text(request: EmbeddingRequest):
    global request_count

    if model is None or tokenizer is None:
        raise HTTPException(status_code=503, detail="Model not loaded")
    
    if not request.text.strip():
        raise HTTPException(status_code=400, detail="Text cannot be empty")

    try:
        start_time = time.time()

        # Tokenize input
        inputs = tokenizer(
            request.text,
            return_tensors="pt",
            truncation=True,
            max_length=512  # E5-Large typical limit
        ).to(device)

        # Generate embeddings
        with torch.no_grad():
            model_output = model(**inputs)
            # Mean pooling over last hidden states
            embeddings = model_output.last_hidden_state.mean(dim=1)
            embedding_list = embeddings[0].cpu().tolist()

        processing_time = time.time() - start_time
        request_count += 1

        return EmbeddingResponse(
            embedding=embedding_list,
            processing_time=processing_time
        )

    except Exception as e:
        logger.error(f"[ERROR] Error generating embedding: {e}")
        raise HTTPException(status_code=500, detail=f"Error generating embedding: {str(e)}")

# Get service statistics
@app.get("/stats")
async def get_stats():

    global request_count
    
    return {
        "total_requests": request_count,
        "model_loaded": model is not None,
        "device": str(device) if device else "unknown",
        "model_name": "sentence-transformers/all-MiniLM-L6-v2",
        "vector_dimension": 384
    }

# Root endpoint with API documentation
@app.get("/")
async def root():

    return {
        "service": "Document Embedding Service",
        "model": "sentence-transformers/all-MiniLM-L6-v2",
        "vector_size": 384,
        "endpoints": {
            "/health": "Health check and service stats",
            "/encode": "Generate single embedding (POST with {text: 'your text'})",
            "/stats": "Get service statistics"
        }
    }

# Error handlers
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    logger.error(f"[ERROR] Unhandled error: {exc}")
    return {"error": "Internal server error", "detail": str(exc)}

if __name__ == "__main__":
    print("[INFO] Starting Document Embedding Service")
    print("[INFO] Service will be available at http://0.0.0.0:8080")

    # Run the service
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8080,
        log_level="info",
        access_log=True
    )