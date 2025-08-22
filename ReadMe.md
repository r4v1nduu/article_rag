## Installation & Setup

### Step 1: Run Docker Containers

### Step 2: Start Embedding Service

```bash
python embedding_service.py
```

### Step 3: Start MongoDB Producer

```bash
# This creates STAGE 1 stream: raw_document_changes
python mongo_producer.py
```

### Step 4: Start Embedding Processor

```bash
# This consumes STAGE 1 and creates STAGE 2 stream: embedded_documents
python embedding_processor.py
```

### Step 5: Start Qdrant Upserter

```bash
# This consumes STAGE 2 and writes to Qdrant
python qdrant_consumer.py
```

---

```bash
# Test Script for RAG Service
curl -X POST "http://your-rag-service:8000/ask" \
     -H "Content-Type: application/json" \
     -d '{"query": "hi"}'
```
