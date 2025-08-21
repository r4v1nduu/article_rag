import os
import asyncio
import logging
from typing import List, Optional
import aiohttp
import requests
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from qdrant_client import AsyncQdrantClient
from qdrant_client.http import models
import time

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration from environment variables
QDRANT_HOST = os.getenv("QDRANT_HOST", "172.30.0.57")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", 6333))
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://172.30.0.58:11434/api/chat")
EMBEDDING_SERVICE_URL = os.getenv("EMBEDDING_SERVICE_URL", "http://172.30.0.59:8080")
COLLECTION_NAME = os.getenv("COLLECTION_NAME", "documents")
REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", 30))

# FastAPI app
app = FastAPI(
    title="RAG Service",
    description="Retrieval-Augmented Generation service using Qdrant and Ollama",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request/Response models
class QueryRequest(BaseModel):
    query: str = Field(..., min_length=1, description="The question to ask")
    top_k: int = Field(5, ge=1, le=20, description="Number of documents to retrieve")
    model: str = Field("mistral:latest", description="Ollama model to use")

class QueryResponse(BaseModel):
    answer: str
    sources_count: int
    processing_time: float
    retrieved_documents: Optional[List[str]] = None

class HealthResponse(BaseModel):
    status: str
    services: dict
    timestamp: str

# Global variables
qdrant_client = None
total_requests = 0

async def initialize_qdrant():
    """Initialize Qdrant client"""
    global qdrant_client
    try:
        logger.info(f"Connecting to Qdrant at {QDRANT_HOST}:{QDRANT_PORT}")
        qdrant_client = AsyncQdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)
        
        # Test connection
        collections = await qdrant_client.get_collections()
        logger.info(f"Connected to Qdrant. Available collections: {[c.name for c in collections.collections]}")
        
        # Check if our collection exists
        try:
            collection_info = await qdrant_client.get_collection(COLLECTION_NAME)
            logger.info(f"Collection '{COLLECTION_NAME}' found with {collection_info.points_count} points")
        except Exception as e:
            logger.warning(f"Collection '{COLLECTION_NAME}' not found: {e}")
            
    except Exception as e:
        logger.error(f"Failed to connect to Qdrant: {e}")
        raise

async def get_embedding(text: str) -> List[float]:
    """Get embedding from remote embedding service"""
    try:
        async with aiohttp.ClientSession() as session:
            payload = {"text": text}
            async with session.post(
                f"{EMBEDDING_SERVICE_URL}/encode",
                json=payload,
                timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise HTTPException(
                        status_code=500,
                        detail=f"Embedding service error: {response.status} - {error_text}"
                    )
                
                result = await response.json()
                return result["embedding"]
                
    except aiohttp.ClientError as e:
        logger.error(f"Error calling embedding service: {e}")
        raise HTTPException(
            status_code=503,
            detail=f"Embedding service unavailable: {str(e)}"
        )

async def retrieve_context(query: str, top_k: int = 5) -> List[str]:
    """Search Qdrant for relevant documents"""
    try:
        # Get query embedding
        query_vector = await get_embedding(query)
        
        # Search in Qdrant
        search_result = await qdrant_client.search(
            collection_name=COLLECTION_NAME,
            query_vector=query_vector,
            limit=top_k,
            with_payload=True
        )
        
        if not search_result:
            logger.info("No relevant documents found")
            return []
        
        # Extract text from results - prioritize full content over preview
        documents = []
        for hit in search_result:
            text_content = None
            
            # Try to get full content first, then fallback to preview
            for field in ["content_full", "content", "content_preview", "text", "body", "subject"]:
                if field in hit.payload and hit.payload[field] and str(hit.payload[field]).strip():
                    text_content = str(hit.payload[field]).strip()
                    logger.info(f"Found content in field '{field}': {text_content[:100]}...")
                    break
            
            if text_content:
                documents.append(text_content)
                logger.debug(f"Found document with score: {hit.score:.4f}, field: {field}")
            else:
                logger.warning(f"No text content found in payload. Available fields: {list(hit.payload.keys())}")
        
        logger.info(f"Retrieved {len(documents)} documents for query: '{query[:100]}...'")
        return documents
        
    except Exception as e:
        logger.error(f"Error retrieving context: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving context: {str(e)}"
        )

def truncate_context(context_text: str, max_chars: int = 8000) -> str:
    """Truncate context to avoid Ollama timeouts while preserving structure"""
    if len(context_text) <= max_chars:
        return context_text
    
    # Try to truncate at sentence boundaries
    truncated = context_text[:max_chars]
    
    # Find the last complete sentence
    last_period = truncated.rfind('.')
    last_newline = truncated.rfind('\n')
    
    # Use the later of period or newline to maintain readability
    cut_point = max(last_period, last_newline)
    
    if cut_point > max_chars * 0.7:  # Only use if we don't lose too much
        return truncated[:cut_point + 1] + "\n\n[Content truncated for processing...]"
    else:
        return truncated + "\n\n[Content truncated for processing...]"

async def ask_ollama(prompt: str, model: str = "mistral:latest") -> str:
    """Send query to Ollama with proper error handling and timeout"""
    try:
        # Truncate prompt if it's too long
        prompt = truncate_context(prompt, max_chars=8000)
        
        payload = {
            "model": model,
            "messages": [
                {
                    "role": "system",
                    "content": "You are a helpful assistant. Answer questions based only on the provided context. Be concise and accurate."
                },
                {
                    "role": "user", 
                    "content": prompt
                }
            ],
            "stream": False
        }
        
        logger.info(f"Sending request to Ollama with {len(prompt)} character prompt")
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                OLLAMA_URL,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=300)  # 5 minute timeout
            ) as response:
                response_text = await response.text()
                logger.info(f"Ollama response status: {response.status}")
                
                if response.status != 200:
                    logger.error(f"Ollama error response: {response_text}")
                    raise HTTPException(
                        status_code=500,
                        detail=f"Ollama error: {response.status} - {response_text}"
                    )
                
                try:
                    result = await response.json()
                    return result["message"]["content"]
                except Exception as parse_error:
                    logger.error(f"Failed to parse Ollama response: {parse_error}")
                    logger.error(f"Raw response: {response_text}")
                    raise HTTPException(
                        status_code=500,
                        detail=f"Failed to parse Ollama response: {parse_error}"
                    )
                
    except asyncio.TimeoutError:
        logger.error("Ollama request timed out")
        raise HTTPException(
            status_code=504,
            detail="Request to language model timed out. Try a shorter query."
        )
    except aiohttp.ClientError as e:
        logger.error(f"Error calling Ollama: {e}")
        raise HTTPException(
            status_code=503,
            detail=f"Ollama service unavailable: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Unexpected error calling Ollama: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Unexpected error with language model: {str(e)}"
        )

@app.on_event("startup")
async def startup_event():
    """Initialize services on startup"""
    logger.info("Starting RAG service...")
    await initialize_qdrant()
    
    # Test embedding service
    try:
        test_embedding = await get_embedding("test")
        logger.info(f"Embedding service connected. Vector dimension: {len(test_embedding)}")
    except Exception as e:
        logger.error(f"Embedding service test failed: {e}")
    
    logger.info("RAG service ready!")

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    if qdrant_client:
        await qdrant_client.close()
    logger.info("RAG service stopped")

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    services = {"qdrant": "unknown", "ollama": "unknown", "embeddings": "unknown"}
    
    # Check Qdrant
    try:
        if qdrant_client:
            await qdrant_client.get_collections()
            services["qdrant"] = "healthy"
    except Exception:
        services["qdrant"] = "unhealthy"
    
    # Check Embedding service
    try:
        await get_embedding("health check")
        services["embeddings"] = "healthy"
    except Exception:
        services["embeddings"] = "unhealthy"
    
    # Check Ollama with a simple request
    try:
        simple_prompt = "Say 'OK' if you can respond."
        await ask_ollama(simple_prompt, "mistral:latest")
        services["ollama"] = "healthy"
    except Exception:
        services["ollama"] = "unhealthy"
    
    status = "healthy" if all(s == "healthy" for s in services.values()) else "degraded"
    
    return HealthResponse(
        status=status,
        services=services,
        timestamp=str(int(time.time()))
    )

@app.post("/ask", response_model=QueryResponse)
async def ask_question(request: QueryRequest):
    """Main RAG endpoint"""
    global total_requests
    
    start_time = time.time()
    total_requests += 1
    
    try:
        # Validate input
        query = request.query.strip()
        if not query:
            raise HTTPException(status_code=400, detail="Query cannot be empty")
        
        logger.info(f"Processing query: '{query[:100]}...'")
        
        # Step 1: Retrieve relevant documents
        context_docs = await retrieve_context(query, request.top_k)
        
        # Step 2: Handle no results
        if not context_docs:
            processing_time = time.time() - start_time
            logger.info(f"No relevant documents found for query")
            return QueryResponse(
                answer="I couldn't find relevant information in the database to answer your question.",
                sources_count=0,
                processing_time=processing_time
            )
        
        # Step 3: Build prompt with retrieved context
        context_text = "\n\n---\n\n".join(context_docs)
        
        # Limit total context size to prevent Ollama timeouts
        context_text = truncate_context(context_text, max_chars=6000)
        
        prompt = f"""Answer the question using ONLY the information provided in the context below. 
If the answer cannot be found in the context, clearly state that you don't have enough information.
Be specific and cite relevant parts of the context when possible.

Context:
{context_text}

Question: {query}

Answer:"""
        
        # Step 4: Generate answer using Ollama
        logger.info(f"Generating answer using model: {request.model}")
        answer = await ask_ollama(prompt, request.model)
        
        processing_time = time.time() - start_time
        
        logger.info(f"Generated answer in {processing_time:.2f}s using {len(context_docs)} sources")
        
        return QueryResponse(
            answer=answer,
            sources_count=len(context_docs),
            processing_time=processing_time,
            retrieved_documents=context_docs[:3] if request.top_k <= 10 else None  # Limit returned docs
        )
        
    except HTTPException:
        raise
    except Exception as e:
        processing_time = time.time() - start_time
        logger.error(f"Unexpected error processing query: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )

@app.get("/debug/collections")
async def debug_collections():
    """Debug endpoint to see what collections exist"""
    try:
        collections = await qdrant_client.get_collections()
        return {
            "available_collections": [c.name for c in collections.collections],
            "current_collection": COLLECTION_NAME,
            "collection_details": [
                {
                    "name": c.name,
                    "status": c.status,
                    "vectors_count": getattr(c, 'vectors_count', 'unknown'),
                    "points_count": getattr(c, 'points_count', 'unknown')
                } for c in collections.collections
            ]
        }
    except Exception as e:
        return {"error": str(e)}

@app.get("/debug/search/{query}")
async def debug_search(query: str):
    """Debug endpoint to see what's in the search results"""
    try:
        query_vector = await get_embedding(query)
        search_result = await qdrant_client.search(
            collection_name=COLLECTION_NAME,
            query_vector=query_vector,
            limit=3,  # Just get a few for debugging
            with_payload=True
        )
        
        debug_info = []
        for hit in search_result:
            debug_info.append({
                "score": hit.score,
                "payload_keys": list(hit.payload.keys()),
                "content_preview": str(hit.payload.get("content_preview", ""))[:200],
                "content_full_length": len(str(hit.payload.get("content_full", "")))
            })
        
        return {"debug_results": debug_info}
    except Exception as e:
        return {"error": str(e)}

@app.get("/stats")
async def get_stats():
    """Get service statistics"""
    try:
        collection_info = await qdrant_client.get_collection(COLLECTION_NAME)
        points_count = collection_info.points_count
    except Exception:
        points_count = "unknown"
    
    return {
        "total_requests": total_requests,
        "collection_name": COLLECTION_NAME,
        "documents_in_collection": points_count,
        "services": {
            "qdrant": f"{QDRANT_HOST}:{QDRANT_PORT}",
            "ollama": OLLAMA_URL,
            "embeddings": EMBEDDING_SERVICE_URL
        }
    }

@app.get("/")
async def root():
    """Root endpoint with API information"""
    return {
        "service": "RAG (Retrieval-Augmented Generation) Service",
        "description": "Ask questions and get answers based on your document collection",
        "endpoints": {
            "/ask": "Ask a question (POST with query, top_k, model)",
            "/health": "Check service health",
            "/stats": "Get service statistics",
            "/debug/collections": "Debug collections",
            "/debug/search/{query}": "Debug search results",
            "/docs": "Interactive API documentation"
        },
        "example_request": {
            "query": "What is the main topic discussed in the documents?",
            "top_k": 5,
            "model": "mistral:latest"
        }
    }

# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled error on {request.method} {request.url}: {exc}")
    return {"error": "Internal server error", "detail": str(exc), "path": str(request.url)}

if __name__ == "__main__":
    import uvicorn
    
    print("Starting RAG Service...")
    print(f"Service will be available at http://0.0.0.0:8000")
    print(f"API docs at http://0.0.0.0:8000/docs")
    print(f"Using Qdrant at {QDRANT_HOST}:{QDRANT_PORT}")
    print(f"Using Ollama at {OLLAMA_URL}")
    print(f"Using Embedding service at {EMBEDDING_SERVICE_URL}")
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info",
        access_log=True
    )