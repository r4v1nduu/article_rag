import os
import json
import time
import logging
import requests
from datetime import datetime
import redis

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

REDIS_HOST = os.getenv("REDIS_HOST")
REDIS_PORT = os.getenv("REDIS_PORT")
EMBEDDING_HOST = os.getenv("EMBEDDING_HOST")
EMBEDDING_PORT = os.getenv("EMBEDDING_PORT")

class EmbeddingProcessor:
    def __init__(self, redis_host, redis_port, embedding_host, embedding_port):
        # Redis connection
        self.redis_client = redis.Redis(
            host=redis_host, 
            port=redis_port, 
            db=0,
            decode_responses=True
        )
        
        # Embedding service endpoint
        self.embedding_url = f"http://{embedding_host}:{embedding_port}/encode"
        
        # Stream configuration
        self.input_stream = 'raw_document_changes'      # STAGE 1: Raw docs
        self.output_stream = 'embedded_documents'       # STAGE 2: Embedded docs
        self.consumer_group = 'embedding_processors'
        self.consumer_name = f'embedder_{int(time.time())}'
        
        # Test connections
        self._test_connections()
        self._setup_consumer_group()
    
    def _test_connections(self):
        try:
            # Test Redis
            self.redis_client.ping()
            logger.info("[INFO] Redis connected successfully")
            
            # Test embedding service
            test_response = requests.post(
                self.embedding_url, 
                json={"text": "test"},
                timeout=10
            )
            if test_response.status_code == 200:
                logger.info("[INFO] Embedding service connected successfully")
            else:
                raise Exception(f"Embedding service returned {test_response.status_code}")
                
        except Exception as e:
            logger.error(f"[ERROR] Connection failed: {e}")
            raise
    
    # Create Redis consumer group for input stream
    def _setup_consumer_group(self):

        try:
            # Try to create consumer group (will fail if already exists)
            self.redis_client.xgroup_create(
                self.input_stream, 
                self.consumer_group, 
                id='0', 
                mkstream=True
            )
            logger.info(f"[INFO] Created consumer group: {self.consumer_group}")
        except redis.exceptions.ResponseError as e:
            if "BUSYGROUP" in str(e):
                logger.info(f"[INFO] Consumer group already exists: {self.consumer_group}")
            else:
                raise
    
    # Get embedding from embedding service with retry logic
    def _get_embedding(self, text):

        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = requests.post(
                    self.embedding_url,
                    json={"text": text},
                    timeout=30
                )
                response.raise_for_status()
                return response.json()["embedding"]
                
            except Exception as e:
                if attempt == max_retries - 1:  # Last attempt
                    logger.error(f"[ERROR] Failed to get embedding after {max_retries} attempts: {e}")
                    raise
                else:
                    wait_time = 2 ** attempt  # Exponential backoff
                    logger.warning(f"[WARNING] Embedding attempt {attempt + 1} failed, retrying in {wait_time}s: {e}")
                    time.sleep(wait_time)
    
    # Process raw document and generate embedded version
    def _process_raw_message(self, message_id, message_data):

        try:
            operation = message_data.get('operation')
            doc_id = message_data.get('doc_id')
            
            if operation == 'delete':
                # For deletes, just pass through to stage 2
                embedded_message = {
                    'operation': 'delete',
                    'doc_id': doc_id,
                    'timestamp': datetime.now().isoformat(),
                    'stage': 'embedded',
                    'original_timestamp': message_data.get('timestamp')
                }

                logger.info(f"[INFO] [STAGE 1→2] Passing delete: {doc_id}")

            elif operation in ['insert', 'update']:
                # Prepare text for embedding (combine relevant fields)
                text_parts = []
                for field in ['subject', 'content']:
                    if message_data.get(field):
                        text_parts.append(message_data[field])
                
                text_to_embed = " ".join(text_parts)
                
                if not text_to_embed.strip():
                    logger.warning(f"[WARNING] No text to embed for {doc_id}, skipping")
                    # Acknowledge and skip
                    self.redis_client.xack(self.input_stream, self.consumer_group, message_id)
                    return
                
                # Get embedding with retry logic
                logger.info(f"[INFO] Generating embedding for {doc_id}")
                vector = self._get_embedding(text_to_embed)
                
                # Create embedded document message
                embedded_message = {
                    'operation': operation,
                    'doc_id': doc_id,
                    'product': message_data.get('product', ''),
                    'customer': message_data.get('customer', ''),
                    'owner': message_data.get('owner', ''),
                    'date': message_data.get('date', ''),
                    'subject': message_data.get('subject', ''),
                    'content': message_data.get('content', ''),
                    'vector': json.dumps(vector),  # Serialize vector as JSON
                    'vector_size': len(vector),
                    'timestamp': datetime.now().isoformat(),
                    'stage': 'embedded',
                    'original_timestamp': message_data.get('timestamp')
                }

                logger.info(f"[INFO] [STAGE 1→2] Generated embedding for {doc_id} (size: {len(vector)})")

            # Send to Stage 2 stream
            embedded_message_id = self.redis_client.xadd(
                self.output_stream,
                embedded_message,
                maxlen=10000
            )
            
            # Acknowledge original message only after successful forwarding
            self.redis_client.xack(self.input_stream, self.consumer_group, message_id)

            logger.info(f"[INFO] [STAGE 1→2] Forwarded to embedded stream: {embedded_message_id}")

        except Exception as e:
            logger.error(f"[ERROR] Failed to process message {message_id}: {e}")
            # Don't acknowledge failed messages - they'll be retried
            raise
    
    # Start processing raw documents and generating embeddings
    def start_processing(self):

        logger.info(f"[INFO] Starting embedding processor: {self.consumer_name}")
        logger.info(f"[INFO] Reading from: {self.input_stream}")
        logger.info(f"[INFO] Writing to: {self.output_stream}")

        while True:
            try:
                # Read messages from Stage 1 stream
                messages = self.redis_client.xreadgroup(
                    self.consumer_group,
                    self.consumer_name,
                    {self.input_stream: '>'},
                    count=5,  # Process fewer at once due to embedding overhead
                    block=5000  # Block for 5 seconds if no messages
                )
                
                if not messages:
                    logger.debug("No new raw documents, waiting")
                    continue
                
                # Process each raw document
                for stream_name, stream_messages in messages:
                    for message_id, fields in stream_messages:
                        try:
                            self._process_raw_message(message_id, fields)
                        except Exception as e:
                            logger.error(f"[ERROR] Error processing {message_id}: {e}")
                            time.sleep(2)  # Brief pause before continuing
                            
            except KeyboardInterrupt:
                logger.info("[INFO] Shutting down embedding processor")
                break
            except Exception as e:
                logger.error(f"[ERROR] Embedding processor error: {e}")
                time.sleep(5)  # Wait before retrying
    
    # Handle any pending/failed messages
    def handle_pending_messages(self):

        try:
            pending = self.redis_client.xpending_range(
                self.input_stream,
                self.consumer_group,
                min='-',
                max='+',
                count=100
            )
            
            if pending:
                logger.info(f"[INFO] Found {len(pending)} pending raw messages, processing")

                for msg_info in pending:
                    message_id = msg_info['message_id']
                    
                    # Claim and process the message
                    claimed = self.redis_client.xclaim(
                        self.input_stream,
                        self.consumer_group,
                        self.consumer_name,
                        min_idle_time=60000,  # 1 minute
                        message_ids=[message_id]
                    )
                    
                    if claimed:
                        _, fields = claimed[0]
                        self._process_raw_message(message_id, fields)
                        
        except Exception as e:
            logger.error(f"[ERROR] Error handling pending messages: {e}")

if __name__ == "__main__":

    # Create and start embedding processor
    processor = EmbeddingProcessor(
        redis_host=REDIS_HOST,
        redis_port=REDIS_PORT,
        embedding_host=EMBEDDING_HOST,
        embedding_port=EMBEDDING_PORT
    )
    
    try:
        # Handle any pending messages first
        processor.handle_pending_messages()
        
        # Start processing new messages
        processor.start_processing()
        
    except KeyboardInterrupt:
        print("\n[INFO] Shutting down gracefully")
    except Exception as e:
        print(f"[ERROR] Fatal error: {e}")
