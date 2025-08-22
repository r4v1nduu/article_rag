import os
import json
import time
import logging
import redis
import uuid
from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, VectorParams, PointStruct

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

REDIS_HOST = os.getenv("REDIS_HOST", "172.30.0.57")
REDIS_PORT = os.getenv("REDIS_PORT", 6379)
QDRANT_HOST = os.getenv("QDRANT_HOST", "172.30.0.57")
QDRANT_PORT = os.getenv("QDRANT_PORT", 6333)

class QdrantUpserter:
    def __init__(self, redis_host, redis_port, qdrant_host, qdrant_port):
        # Redis connection
        self.redis_client = redis.Redis(
            host=redis_host, 
            port=redis_port, 
            db=0,
            decode_responses=True
        )
        
        # Qdrant connection
        self.qdrant_client = QdrantClient(
            host=qdrant_host,
            port=qdrant_port
        )
        
        # Stream configuration
        self.input_stream = 'embedded_documents' # STAGE 2: Embedded docs
        self.consumer_group = 'qdrant_upserters'
        self.consumer_name = f'upserter_{int(time.time())}'
        self.collection_name = 'documents'
        
        # Test connections
        self._test_connections()
        self._setup_qdrant_collection()
        self._setup_consumer_group()
    
    def _test_connections(self):
        try:
            # Test Redis
            self.redis_client.ping()
            logger.info("[INFO] Redis connected successfully")

            # Test Qdrant
            collections = self.qdrant_client.get_collections()
            logger.info("[INFO] Qdrant connected successfully")

        except Exception as e:
            logger.error(f"[ERROR] Connection failed: {e}")
            raise
    
    # Create Qdrant collection if it doesn't exist
    def _setup_qdrant_collection(self):

        try:
            collections = self.qdrant_client.get_collections().collections
            collection_names = [col.name for col in collections]
            
            if self.collection_name not in collection_names:
                self.qdrant_client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=VectorParams(
                        size=384,  # all-MiniLM-L6-v2 produces 384-dim vectors
                        distance=Distance.COSINE
                    )
                )
                logger.info(f"[INFO] Created Qdrant collection: {self.collection_name}")
            else:
                logger.info(f"[INFO] Qdrant collection exists: {self.collection_name}")

        except Exception as e:
            logger.error(f"[ERROR] Failed to setup Qdrant collection: {e}")
            raise
    
    # Create Redis consumer group for embedded documents stream
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
    
    # Convert MongoDB ObjectId to deterministic UUID
    def _mongodb_id_to_uuid(self, mongodb_id):

        # Create a deterministic UUID from MongoDB ObjectId
        # This ensures the same MongoDB ID always maps to the same UUID
        namespace = uuid.UUID('6ba7b810-9dad-11d1-80b4-00c04fd430c8')  # Standard namespace
        return str(uuid.uuid5(namespace, str(mongodb_id)))
    
    # Process embedded document and upsert to Qdrant
    def _process_embedded_message(self, message_id, message_data):

        try:
            operation = message_data.get('operation')
            doc_id = message_data.get('doc_id')
            
            if operation == 'delete':
                # Convert MongoDB ObjectId to UUID for deletion
                point_uuid = self._mongodb_id_to_uuid(doc_id)
                
                # Delete from Qdrant with retry logic
                max_retries = 3
                for attempt in range(max_retries):
                    try:
                        self.qdrant_client.delete(
                            collection_name=self.collection_name,
                            points_selector=[point_uuid]
                        )
                        logger.info(f"[INFO] [STAGE 2] Deleted from Qdrant: {doc_id} -> {point_uuid}")
                        break
                    except Exception as e:
                        if attempt == max_retries - 1:
                            raise
                        wait_time = 2 ** attempt
                        logger.warning(f"[WARNING] Delete attempt {attempt + 1} failed, retrying in {wait_time}s: {e}")
                        time.sleep(wait_time)
                
            elif operation in ['insert', 'update']:
                # Parse the vector from JSON
                vector_json = message_data.get('vector')
                if not vector_json:
                    logger.error(f"[ERROR] No vector found for {doc_id}")
                    return
                
                try:
                    vector = json.loads(vector_json)
                except json.JSONDecodeError as e:
                    logger.error(f"[ERROR] Failed to parse vector for {doc_id}: {e}")
                    return
                
                # Validate vector size
                expected_size = 384  # all-MiniLM-L6-v2
                if len(vector) != expected_size:
                    logger.error(f"[ERROR] Wrong vector size for {doc_id}: got {len(vector)}, expected {expected_size}")
                    return
                
                # Convert MongoDB ObjectId to UUID for Qdrant
                point_uuid = self._mongodb_id_to_uuid(doc_id)
                
                # Prepare point for Qdrant
                point = PointStruct(
                    id=point_uuid,
                    vector=vector,
                    payload={
                        'mongodb_id': doc_id,  # Store original MongoDB ID for reference
                        'product': message_data.get('product', ''),
                        'customer': message_data.get('customer', ''),
                        'owner': message_data.get('owner', ''),
                        'date': message_data.get('date', ''),
                        'subject': message_data.get('subject', ''),
                        'content': message_data.get('content', ''),
                        'vector_size': message_data.get('vector_size'),
                        'embedded_timestamp': message_data.get('timestamp'),
                        'original_timestamp': message_data.get('original_timestamp')
                    }
                )
                
                # Upsert to Qdrant with retry logic
                max_retries = 3
                for attempt in range(max_retries):
                    try:
                        self.qdrant_client.upsert(
                            collection_name=self.collection_name,
                            points=[point]
                        )
                        logger.info(f"[INFO] [STAGE 2] Upserted to Qdrant: {operation} - {doc_id} -> {point_uuid}")
                        break
                    except Exception as e:
                        if attempt == max_retries - 1:
                            raise
                        wait_time = 2 ** attempt
                        logger.warning(f"[WARNING] Upsert attempt {attempt + 1} failed, retrying in {wait_time}s: {e}")
                        time.sleep(wait_time)
            
            # Acknowledge message only after successful Qdrant operation
            self.redis_client.xack(self.input_stream, self.consumer_group, message_id)
            logger.debug(f"[DEBUG] Acknowledged embedded message: {message_id}")
            
        except Exception as e:
            logger.error(f"[ERROR] Failed to process embedded message {message_id}: {e}")
            # Don't acknowledge failed messages - they'll be retried
            raise
    
    # Start consuming embedded documents and upserting to Qdrant
    def start_consuming(self):

        logger.info(f"[INFO] Starting Qdrant upserter: {self.consumer_name}")
        logger.info(f"[INFO] Reading from: {self.input_stream}")
        logger.info(f"[INFO] Writing to: Qdrant collection '{self.collection_name}'")

        while True:
            try:
                # Read messages from Stage 2 stream (embedded documents)
                messages = self.redis_client.xreadgroup(
                    self.consumer_group,
                    self.consumer_name,
                    {self.input_stream: '>'},
                    count=10,  # Can process more since no heavy computation
                    block=5000  # Block for 5 seconds if no messages
                )
                
                if not messages:
                    logger.debug("No new embedded documents, waiting")
                    continue
                
                # Process each embedded document
                for stream_name, stream_messages in messages:
                    for message_id, fields in stream_messages:
                        try:
                            self._process_embedded_message(message_id, fields)
                        except Exception as e:
                            logger.error(f"[ERROR] Error processing {message_id}: {e}")
                            time.sleep(1)  # Brief pause before continuing
                            
            except KeyboardInterrupt:
                logger.info("[INFO] Shutting down Qdrant upserter...")
                break
            except Exception as e:
                logger.error(f"[ERROR] Qdrant upserter error: {e}")
                time.sleep(5)  # Wait before retrying
    
    # Handle any pending/failed embedded messages
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
                logger.info(f"[INFO] Found {len(pending)} pending embedded messages, processing")

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
                        self._process_embedded_message(message_id, fields)
                        
        except Exception as e:
            logger.error(f"[ERROR] Error handling pending messages: {e}")

    # Get processing statistics
    def get_stats(self):

        try:
            # Stream info
            stream_info = self.redis_client.xinfo_stream(self.input_stream)
            
            # Consumer group info
            group_info = self.redis_client.xinfo_groups(self.input_stream)
            
            # Qdrant collection info
            collection_info = self.qdrant_client.get_collection(self.collection_name)
            
            stats = {
                'stream_length': stream_info['length'],
                'consumer_groups': len(group_info),
                'qdrant_points': collection_info.points_count,
                'qdrant_vectors_count': collection_info.vectors_count
            }
            
            logger.info(f"[INFO] Stats: {stats}")
            return stats
            
        except Exception as e:
            logger.error(f"[ERROR] Error getting stats: {e}")
            return {}

if __name__ == "__main__":

    # Create and start Qdrant upserter
    upserter = QdrantUpserter(
        redis_host=REDIS_HOST,
        redis_port=REDIS_PORT,
        qdrant_host=QDRANT_HOST,
        qdrant_port=QDRANT_PORT
    )
    
    try:
        # Handle any pending messages first
        upserter.handle_pending_messages()
        
        # Show initial stats
        upserter.get_stats()
        
        # Start consuming embedded documents
        upserter.start_consuming()
        
    except KeyboardInterrupt:
        print("\n[INFO] Shutting down gracefully")
        # Show final stats
        upserter.get_stats()
    except Exception as e:
        print(f"[ERROR] Fatal error: {e}")
