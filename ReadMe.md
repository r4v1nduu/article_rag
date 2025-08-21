For App : Create `.env.local`:

```
# MongoDB Configuration
MONGODB_URI=
DATABASE_NAME=
COLLECTION_NAME=

# Elasticsearch Configuration
ELASTICSEARCH_URL=
ELASTICSEARCH_INDEX=

# Node.js Environment
NODE_ENV=development
```

---

## Architecture Overview
```
MongoDB (172.30.0.57:27017) 
    ↓ [change streams]
📥 STAGE 1: Redis Stream "raw_document_changes"
    ↓ [Consumer A: Embedding Processor]
🧠 Embedding Service (172.30.0.59:8080)
    ↓ [generates vectors]
📤 STAGE 2: Redis Stream "embedded_documents" 
    ↓ [Consumer B: Qdrant Upserter]
🎯 Qdrant (172.30.0.57:6333)
```

## Installation & Setup

### Step 1: Start Embedding Service (172.30.0.59)
```bash
# Save embedding_service.py and run:
python embedding_service.py

# Test it:
curl -X POST "http://172.30.0.59:8080/encode" \
     -H "Content-Type: application/json" \
     -d '{"text": "This is a test document"}'
```

### Step 2: Start MongoDB Producer (172.30.0.57)
```bash
# This creates STAGE 1 stream: raw_document_changes
python mongo_producer.py
```

### Step 3: Start Embedding Processor (172.30.0.57)
```bash
# This consumes STAGE 1 and creates STAGE 2 stream: embedded_documents
python embedding_processor.py
```

### Step 4: Start Qdrant Upserter (172.30.0.57)
```bash
# This consumes STAGE 2 and writes to Qdrant
python qdrant_consumer.py
```

---

## RAG

``` bash
# Test Script
curl -X POST "http://your-rag-service:8000/ask" \
     -H "Content-Type: application/json" \
     -d '{"query": "change crowdstrike agent id"}'
```

