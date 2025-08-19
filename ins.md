# Two-Stage MongoDB → Redis Streams → Qdrant Pipeline

## 🏗️ Architecture Overview
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

## 🛡️ Fault Tolerance Benefits

### **Complete Isolation:**
- **Embedding service down** → Stage 1 stream buffers raw documents
- **Qdrant down** → Stage 2 stream buffers embedded documents  
- **Either fails** → No data loss, automatic retry when back online

### **Independent Scaling:**
- Scale embedding processors separately from Qdrant upserters
- Monitor bottlenecks at each stage independently
- Replay from any stage if needed

## 🚀 Installation & Setup

### Dependencies (172.30.0.57)
```bash
pip install pymongo redis-py qdrant-client requests
```

### Dependencies (172.30.0.59)
```bash
pip install fastapi uvicorn sentence-transformers torch
```

## 📋 Step-by-Step Setup

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

## 🧪 Testing the Pipeline

### 1. Insert Test Document
```javascript
use your_database_name
db.your_collection_name.insertOne({
    product: "Test Product",
    customer: "Test Customer", 
    owner: "Test Owner",
    date: new Date(),
    subject: "AI and Machine Learning",
    content: "This document discusses artificial intelligence and machine learning applications in modern software development."
})
```

### 2. Monitor Redis Streams
```bash
redis-cli -h 172.30.0.57

# Check STAGE 1: Raw documents
XRANGE raw_document_changes - +
XLEN raw_document_changes

# Check STAGE 2: Embedded documents  
XRANGE embedded_documents - +
XLEN embedded_documents

# Monitor consumer groups
XINFO GROUPS raw_document_changes
XINFO GROUPS embedded_documents

# Check pending messages
XPENDING raw_document_changes embedding_processors
XPENDING embedded_documents qdrant_upserters
```

### 3. Verify Qdrant
```bash
# Check collection
curl "http://172.30.0.57:6333/collections/documents"

# Check points count
curl "http://172.30.0.57:6333/collections/documents/points"

# Search test
curl -X POST "http://172.30.0.57:6333/collections/documents/points/search" \
     -H "Content-Type: application/json" \
     -d '{
       "vector": [0.1, 0.2, 0.3, ...],  
       "limit": 5
     }'
```

## 🔧 Operational Commands

### Monitor Pipeline Health
```bash
# Check stream lengths
redis-cli -h 172.30.0.57 XLEN raw_document_changes
redis-cli -h 172.30.0.57 XLEN embedded_documents

# Check consumer lag
redis-cli -h 172.30.0.57 XINFO GROUPS raw_document_changes
redis-cli -h 172.30.0.57 XINFO GROUPS embedded_documents
```

### Handle Failures

**Embedding Service Down:**
```bash
# Raw documents will queue up in STAGE 1
redis-cli XLEN raw_document_changes  # This will grow

# When service comes back online, processing resumes automatically
# Check pending messages:
redis-cli XPENDING raw_document_changes embedding_processors
```

**Qdrant Down:**
```bash
# Embedded documents will queue up in STAGE 2
redis-cli XLEN embedded_documents  # This will grow

# When Qdrant comes back, processing resumes automatically
redis-cli XPENDING embedded_documents qdrant_upserters
```

**Clear Stuck Messages:**
```bash
# If messages get stuck, claim them back
redis-cli XCLAIM raw_document_changes embedding_processors consumer_name 60000 message_id
```

### Scaling Operations

**Add More Embedding Processors:**
```bash
# Just run more instances - they'll auto-balance
python embedding_processor.py  # Instance 2
python embedding_processor.py  # Instance 3
```

**Add More Qdrant Upserters:**
```bash
# Run multiple upserters for faster Qdrant writes
python qdrant_consumer.py  # Instance 2
python qdrant_consumer.py  # Instance 3
```

## 📊 Monitoring & Alerting

### Key Metrics to Watch

**Stream Lengths:**
- `raw_document_changes` length - should stay low if embedding is keeping up
- `embedded_documents` length - should stay low if Qdrant is keeping up

**Consumer Lag:**
```bash
# Check if consumers are falling behind
XINFO GROUPS raw_document_changes
XINFO GROUPS embedded_documents
```

**Error Patterns:**
- Embedding service timeouts
- Qdrant connection failures
- Large vector sizes (memory issues)

### Set Up Alerts
```bash
# Example: Alert if Stage 1 queue gets too long
if [ $(redis-cli XLEN raw_document_changes) -gt 1000 ]; then
    echo "ALERT: Raw documents queue is backing up!"
fi

# Alert if Stage 2 queue gets too long  
if [ $(redis-cli XLEN embedded_documents) -gt 500 ]; then
    echo "ALERT: Embedded documents queue is backing up!"
fi
```

## 🔄 Recovery Scenarios

### Complete System Recovery
```bash
# 1. Start embedding service first
python embedding_service.py

# 2. Start MongoDB producer  
python mongo_producer.py

# 3. Start embedding processor
python embedding_processor.py

# 4. Start Qdrant upserter
python qdrant_consumer.py

# System will automatically process any queued messages
```

### Rebuild Qdrant from Scratch
```bash
# 1. Stop Qdrant upserter
# 2. Clear Qdrant collection
curl -X DELETE "http://172.30.0.57:6333/collections/documents"

# 3. Reset Stage 2 consumer group to replay all embedded docs
redis-cli XGROUP DESTROY embedded_documents qdrant_upserters
redis-cli XGROUP CREATE embedded_documents qdrant_upserters 0

# 4. Restart Qdrant upserter - it will reprocess all embedded documents
python qdrant_consumer.py
```

### Replay from MongoDB
```bash
# If you need to completely rebuild everything:
# 1. Stop all consumers
# 2. Clear both streams
redis-cli DEL raw_document_changes embedded_documents

# 3. Use MongoDB aggregation to replay changes
# 4. Restart the pipeline
```

## 🎯 Production Optimizations

### Redis Configuration
```ini
# /etc/redis/redis.conf
# Enable persistence for durability
appendonly yes
appendfsync everysec

# Memory management
maxmemory 4gb
maxmemory-policy allkeys-lru

# Stream optimizations
stream-node-max-bytes 4096
stream-node-max-entries 100
```

### Performance Tuning
```python
# In embedding_processor.py - batch embeddings
def _get_embeddings_batch(self, texts):
    """Process multiple texts at once for better throughput"""
    response = requests.post(
        f"{self.embedding_url}_batch",
        json={"texts": texts},
        timeout=60
    )
    return response.json()["embeddings"]
```

### Monitoring Script
```python
# monitor.py
import redis
import time

redis_client = redis.Redis(host='172.30.0.57', port=6379)

while True:
    stage1_len = redis_client.xlen('raw_document_changes')
    stage2_len = redis_client.xlen('embedded_documents')
    
    print(f"Stage 1 Queue: {stage1_len}, Stage 2 Queue: {stage2_len}")
    
    if stage1_len > 1000:
        print("⚠️  WARNING: Stage 1 backing up!")
    if stage2_len > 500:
        print("⚠️  WARNING: Stage 2 backing up!")
        
    time.sleep(30)
```

## 🎉 Summary

This two-stage architecture provides:
- ✅ **Complete fault tolerance** - no single point of failure
- ✅ **Independent scaling** - scale each stage separately  
- ✅ **Message durability** - Redis streams persist messages
- ✅ **Automatic recovery** - consumers resume where they left off
- ✅ **Clear monitoring** - see exactly where bottlenecks occur
- ✅ **Replay capability** - can rebuild Qdrant from embedded documents

Your document pipeline is now production-ready! 🚀