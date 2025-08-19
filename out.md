Perfect! Here's your complete two-stage fault-tolerant pipeline:
🏗️ What You Have Now:
4 Components to run:

🔄 MongoDB Producer - Watches MongoDB changes → Stage 1 stream
🧠 Embedding Processor - Stage 1 stream → Embeddings → Stage 2 stream
🎯 Qdrant Upserter - Stage 2 stream → Qdrant vector DB
📊 Monitor Dashboard - Real-time pipeline health monitoring

🛡️ Fault Tolerance Achieved:
