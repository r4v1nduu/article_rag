import os
import asyncio
import logging
import json
from typing import List, Optional, Dict, Any, AsyncGenerator
import aiohttp
import requests
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from qdrant_client import AsyncQdrantClient
from qdrant_client.http import models
import time
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration from environment variables
QDRANT_HOST = os.getenv("QDRANT_HOST", "172.30.0.57")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", 6333))
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://172.30.0.58:11434")
EMBEDDING_SERVICE_URL = os.getenv("EMBEDDING_SERVICE_URL", "http://172.30.0.59:8080")
COLLECTION_NAME = os.getenv("COLLECTION_NAME", "documents")
REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", 30))
DEFAULT_MODEL = os.getenv("DEFAULT_MODEL", "mistral:latest")
RAG_TOP_K = int(os.getenv("RAG_TOP_K", 5))
RAG_ENABLED = os.getenv("RAG_ENABLED", "true").lower() == "true"

# FastAPI app
app = FastAPI(
    title="Ollama-Compatible RAG Service",
    description="RAG service that mimics Ollama API for compatibility with Open WebUI and other frontends",
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

# Ollama API compatible models
class Message(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    model: str
    messages: List[Message]
    stream: Optional[bool] = False
    options: Optional[Dict[str, Any]] = None

class GenerateRequest(BaseModel):
    model: str
    prompt: str
    stream: Optional[bool] = False
    options: Optional[Dict[str, Any]] = None

class ChatResponse(BaseModel):
    model: str
    created_at: str
    message: Message
    done: bool
    total_duration: Optional[int] = None
    load_duration: Optional[int] = None
    prompt_eval_count: Optional[int] = None
    prompt_eval_duration: Optional[int] = None
    eval_count: Optional[int] = None
    eval_duration: Optional[int] = None

class GenerateResponse(BaseModel):
    model: str
    created_at: str
    response: str
    done: bool
    context: Optional[List[int]] = None
    total_duration: Optional[int] = None
    load_duration: Optional[int] = None
    prompt_eval_count: Optional[int] = None
    prompt_eval_duration: Optional[int] = None
    eval_count: Optional[int] = None
    eval_duration: Optional[int] = None

class ModelInfo(BaseModel):
    name: str
    size: int
    digest: str
    details: Dict[str, Any]
    expires_at: str
    size_vram: int

class TagsResponse(BaseModel):
    models: List[ModelInfo]

# Global variables
qdrant_client = None
total_requests = 0

async def initialize_qdrant():
    """Initialize Qdrant client"""
    global qdrant_client
    if not RAG_ENABLED:
        logger.info("RAG is disabled, skipping Qdrant initialization")
        return
        
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
        if RAG_ENABLED:
            raise

async def get_embedding(text: str) -> List[float]:
    """Get embedding from remote embedding service"""
    if not RAG_ENABLED:
        return []
        
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
    if not RAG_ENABLED or not qdrant_client:
        return []
        
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
        
        # Extract text from results
        documents = []
        for hit in search_result:
            text_content = None
            
            # Try to get full content first, then fallback to preview
            for field in ["content_full", "content", "content_preview", "text", "body", "subject"]:
                if field in hit.payload and hit.payload[field] and str(hit.payload[field]).strip():
                    text_content = str(hit.payload[field]).strip()
                    break
            
            if text_content:
                documents.append(text_content)
                logger.debug(f"Found document with score: {hit.score:.4f}")
        
        logger.info(f"Retrieved {len(documents)} documents for query: '{query[:100]}...'")
        return documents
        
    except Exception as e:
        logger.error(f"Error retrieving context: {e}")
        return []  # Return empty instead of raising error to maintain compatibility

def should_use_rag(messages: List[Message]) -> bool:
    """Determine if RAG should be used based on the conversation"""
    if not RAG_ENABLED:
        return False
        
    # Use RAG for user questions (not system messages or simple greetings)
    last_message = messages[-1] if messages else None
    if not last_message or last_message.role != "user":
        return False
        
    # Skip RAG for very short messages or greetings
    content = last_message.content.lower().strip()
    if len(content) < 10:
        return False
        
    # Skip common greetings
    greetings = ["hi", "hello", "hey", "good morning", "good afternoon", "good evening"]
    if content in greetings:
        return False
        
    return True

def truncate_context(context_text: str, max_chars: int = 6000) -> str:
    """Truncate context to avoid token limits"""
    if len(context_text) <= max_chars:
        return context_text
    
    # Try to truncate at sentence boundaries
    truncated = context_text[:max_chars]
    
    # Find the last complete sentence
    last_period = truncated.rfind('.')
    last_newline = truncated.rfind('\n')
    
    # Use the later of period or newline to maintain readability
    cut_point = max(last_period, last_newline)
    
    if cut_point > max_chars * 0.7:
        return truncated[:cut_point + 1] + "\n\n[Content truncated...]"
    else:
        return truncated + "\n\n[Content truncated...]"

async def enhance_with_rag(messages: List[Message]) -> List[Message]:
    """Enhance messages with RAG context if applicable"""
    if not should_use_rag(messages):
        return messages
        
    last_message = messages[-1]
    query = last_message.content
    
    # Retrieve relevant context
    context_docs = await retrieve_context(query, RAG_TOP_K)
    
    if not context_docs:
        return messages
        
    # Build context
    context_text = "\n\n---\n\n".join(context_docs)
    context_text = truncate_context(context_text)
    
    # Create enhanced messages
    enhanced_messages = messages[:-1].copy()  # All messages except the last
    
    # Add system message with context (or enhance existing system message)
    context_instruction = f"""You are a helpful assistant. Use the following context to answer questions when relevant:

CONTEXT:
{context_text}

Instructions:
- Answer based on the provided context when possible
- If the context doesn't contain relevant information, answer normally using your general knowledge
- Be specific and cite relevant parts when referencing the context
- Don't mention that you're using retrieved context unless asked"""

    # Check if there's already a system message
    has_system_message = any(msg.role == "system" for msg in enhanced_messages)
    
    if has_system_message:
        # Enhance the existing system message
        for i, msg in enumerate(enhanced_messages):
            if msg.role == "system":
                enhanced_messages[i] = Message(
                    role="system",
                    content=f"{msg.content}\n\n{context_instruction}"
                )
                break
    else:
        # Add new system message at the beginning
        enhanced_messages.insert(0, Message(role="system", content=context_instruction))
    
    # Add the original user message
    enhanced_messages.append(last_message)
    
    logger.info(f"Enhanced query with {len(context_docs)} context documents")
    return enhanced_messages

async def call_ollama_chat(request: ChatRequest) -> Dict[str, Any]:
    """Call the actual Ollama chat endpoint"""
    ollama_chat_url = f"{OLLAMA_URL}/api/chat"
    
    async with aiohttp.ClientSession() as session:
        async with session.post(
            ollama_chat_url,
            json=request.dict(),
            timeout=aiohttp.ClientTimeout(total=300)
        ) as response:
            if response.status != 200:
                error_text = await response.text()
                raise HTTPException(
                    status_code=response.status,
                    detail=f"Ollama error: {error_text}"
                )
            
            if request.stream:
                return response
            else:
                return await response.json()

async def call_ollama_generate(request: GenerateRequest) -> Dict[str, Any]:
    """Call the actual Ollama generate endpoint"""
    ollama_generate_url = f"{OLLAMA_URL}/api/generate"
    
    async with aiohttp.ClientSession() as session:
        async with session.post(
            ollama_generate_url,
            json=request.dict(),
            timeout=aiohttp.ClientTimeout(total=300)
        ) as response:
            if response.status != 200:
                error_text = await response.text()
                raise HTTPException(
                    status_code=response.status,
                    detail=f"Ollama error: {error_text}"
                )
            
            if request.stream:
                return response
            else:
                return await response.json()

@app.on_event("startup")
async def startup_event():
    """Initialize services on startup"""
    logger.info("Starting Ollama-compatible RAG service...")
    await initialize_qdrant()
    
    if RAG_ENABLED:
        # Test embedding service
        try:
            test_embedding = await get_embedding("test")
            logger.info(f"Embedding service connected. Vector dimension: {len(test_embedding)}")
        except Exception as e:
            logger.error(f"Embedding service test failed: {e}")
    
    logger.info("Service ready!")

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    if qdrant_client:
        await qdrant_client.close()
    logger.info("Service stopped")

# Ollama API compatible endpoints
@app.post("/api/chat")
async def chat(request: ChatRequest):
    """Ollama-compatible chat endpoint with RAG enhancement"""
    global total_requests
    total_requests += 1
    
    try:
        # Enhance messages with RAG context if needed
        enhanced_messages = await enhance_with_rag(request.messages)
        
        # Create request with enhanced messages
        enhanced_request = ChatRequest(
            model=request.model,
            messages=enhanced_messages,
            stream=request.stream,
            options=request.options
        )
        
        # Call actual Ollama
        if request.stream:
            # Handle streaming response
            async def stream_response():
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        f"{OLLAMA_URL}/api/chat",
                        json=enhanced_request.dict(),
                        timeout=aiohttp.ClientTimeout(total=300)
                    ) as response:
                        if response.status != 200:
                            error_text = await response.text()
                            raise HTTPException(
                                status_code=response.status,
                                detail=f"Ollama error: {error_text}"
                            )
                        
                        async for chunk in response.content:
                            if chunk:
                                yield chunk
            
            return StreamingResponse(
                stream_response(),
                media_type="application/x-ndjson"
            )
        else:
            # Handle non-streaming response
            result = await call_ollama_chat(enhanced_request)
            return result
            
    except Exception as e:
        logger.error(f"Error in chat endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/generate")
async def generate(request: GenerateRequest):
    """Ollama-compatible generate endpoint with RAG enhancement"""
    global total_requests
    total_requests += 1
    
    try:
        # Convert generate request to chat format for RAG processing
        messages = [Message(role="user", content=request.prompt)]
        enhanced_messages = await enhance_with_rag(messages)
        
        # If RAG was applied, convert back to enhanced prompt
        if len(enhanced_messages) > 1:
            # Combine system message and user message into a single prompt
            enhanced_prompt = ""
            for msg in enhanced_messages:
                if msg.role == "system":
                    enhanced_prompt += f"{msg.content}\n\n"
                elif msg.role == "user":
                    enhanced_prompt += f"User: {msg.content}\n\nAssistant:"
            
            enhanced_request = GenerateRequest(
                model=request.model,
                prompt=enhanced_prompt,
                stream=request.stream,
                options=request.options
            )
        else:
            enhanced_request = request
        
        # Call actual Ollama
        if request.stream:
            # Handle streaming response
            async def stream_response():
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        f"{OLLAMA_URL}/api/generate",
                        json=enhanced_request.dict(),
                        timeout=aiohttp.ClientTimeout(total=300)
                    ) as response:
                        if response.status != 200:
                            error_text = await response.text()
                            raise HTTPException(
                                status_code=response.status,
                                detail=f"Ollama error: {error_text}"
                            )
                        
                        async for chunk in response.content:
                            if chunk:
                                yield chunk
            
            return StreamingResponse(
                stream_response(),
                media_type="application/x-ndjson"
            )
        else:
            result = await call_ollama_generate(enhanced_request)
            return result
            
    except Exception as e:
        logger.error(f"Error in generate endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/tags")
async def get_models():
    """Ollama-compatible models endpoint"""
    try:
        # Forward to actual Ollama
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{OLLAMA_URL}/api/tags") as response:
                if response.status != 200:
                    # Fallback response if Ollama is not available
                    return TagsResponse(models=[
                        ModelInfo(
                            name=DEFAULT_MODEL,
                            size=0,
                            digest="rag-enhanced",
                            details={"format": "gguf", "family": "llama", "families": ["llama"]},
                            expires_at="",
                            size_vram=0
                        )
                    ])
                
                result = await response.json()
                return result
                
    except Exception as e:
        logger.error(f"Error getting models: {e}")
        # Fallback response
        return TagsResponse(models=[
            ModelInfo(
                name=DEFAULT_MODEL,
                size=0,
                digest="rag-enhanced",
                details={"format": "gguf", "family": "llama", "families": ["llama"]},
                expires_at="",
                size_vram=0
            )
        ])

@app.get("/api/show")
async def show_model(name: str):
    """Ollama-compatible show model endpoint"""
    try:
        # Forward to actual Ollama
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{OLLAMA_URL}/api/show", params={"name": name}) as response:
                if response.status != 200:
                    raise HTTPException(status_code=404, detail="Model not found")
                
                result = await response.json()
                return result
                
    except Exception as e:
        logger.error(f"Error showing model: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/pull")
async def pull_model(request: dict):
    """Ollama-compatible pull model endpoint"""
    try:
        # Forward to actual Ollama
        async with aiohttp.ClientSession() as session:
            async with session.post(f"{OLLAMA_URL}/api/pull", json=request) as response:
                if request.get("stream", False):
                    async def stream_response():
                        async for chunk in response.content:
                            if chunk:
                                yield chunk
                    
                    return StreamingResponse(
                        stream_response(),
                        media_type="application/x-ndjson"
                    )
                else:
                    result = await response.json()
                    return result
                    
    except Exception as e:
        logger.error(f"Error pulling model: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Health and debug endpoints
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    services = {"ollama": "unknown", "qdrant": "unknown", "embeddings": "unknown"}
    
    # Check Ollama
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{OLLAMA_URL}/api/tags") as response:
                services["ollama"] = "healthy" if response.status == 200 else "unhealthy"
    except Exception:
        services["ollama"] = "unhealthy"
    
    # Check Qdrant
    if RAG_ENABLED:
        try:
            if qdrant_client:
                await qdrant_client.get_collections()
                services["qdrant"] = "healthy"
        except Exception:
            services["qdrant"] = "unhealthy"
    else:
        services["qdrant"] = "disabled"
    
    # Check Embedding service
    if RAG_ENABLED:
        try:
            await get_embedding("health check")
            services["embeddings"] = "healthy"
        except Exception:
            services["embeddings"] = "unhealthy"
    else:
        services["embeddings"] = "disabled"
    
    status = "healthy" if all(s in ["healthy", "disabled"] for s in services.values()) else "degraded"
    
    return {
        "status": status,
        "services": services,
        "rag_enabled": RAG_ENABLED,
        "total_requests": total_requests,
        "timestamp": datetime.now().isoformat()
    }

@app.get("/")
async def root():
    """Root endpoint with service information"""
    return {
        "service": "Ollama-Compatible RAG Service",
        "description": "RAG-enhanced Ollama API for use with Open WebUI and other frontends",
        "rag_enabled": RAG_ENABLED,
        "endpoints": {
            "/api/chat": "Ollama-compatible chat endpoint with RAG",
            "/api/generate": "Ollama-compatible generate endpoint with RAG",
            "/api/tags": "List available models",
            "/api/show": "Show model details",
            "/api/pull": "Pull/download models",
            "/health": "Service health check",
        },
        "configuration": {
            "ollama_url": OLLAMA_URL,
            "rag_enabled": RAG_ENABLED,
            "collection": COLLECTION_NAME if RAG_ENABLED else "disabled",
            "top_k": RAG_TOP_K if RAG_ENABLED else "disabled"
        }
    }

if __name__ == "__main__":
    import uvicorn
    
    print("Starting Ollama-Compatible RAG Service...")
    print(f"Service will be available at http://0.0.0.0:8000")
    print(f"Ollama API compatibility at http://0.0.0.0:8000/api/*")
    print(f"RAG enabled: {RAG_ENABLED}")
    if RAG_ENABLED:
        print(f"Using Qdrant at {QDRANT_HOST}:{QDRANT_PORT}")
        print(f"Using Embedding service at {EMBEDDING_SERVICE_URL}")
    print(f"Proxying to Ollama at {OLLAMA_URL}")
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info",
        access_log=True
    )