import json
import time
import logging
from pymongo import MongoClient
import redis
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MongoChangeStreamProducer:
    def __init__(self, mongo_uri, redis_host, redis_port=6379, redis_db=0):
        # MongoDB connection
        self.mongo_client = MongoClient(mongo_uri)
        
        # TODO: UPDATE THESE WITH YOUR ACTUAL DATABASE AND COLLECTION NAMES
        self.db = self.mongo_client['emaildb']  # ⚠️ CHANGE THIS
        self.collection = self.db['emails']  # ⚠️ CHANGE THIS
        
        # Redis connection
        self.redis_client = redis.Redis(
            host=redis_host, 
            port=redis_port, 
            db=redis_db,
            decode_responses=True
        )
        
        # STAGE 1: Raw document changes stream
        self.raw_stream = 'raw_document_changes'
        
        # Test connections
        self._test_connections()
    
    def _test_connections(self):
        try:
            # Test MongoDB
            self.mongo_client.admin.command('ping')
            logger.info("✅ MongoDB connected successfully")
            
            # Test Redis
            self.redis_client.ping()
            logger.info("✅ Redis connected successfully")
            
        except Exception as e:
            logger.error(f"❌ Connection failed: {e}")
            raise
    
    def _prepare_raw_message(self, change_event):
        """Prepare raw document message for Stage 1 stream"""
        operation = change_event['operationType']
        
        if operation == 'delete':
            return {
                'operation': 'delete',
                'doc_id': str(change_event['documentKey']['_id']),
                'timestamp': datetime.now().isoformat(),
                'stage': 'raw'
            }
        
        # For insert/update operations
        document = change_event.get('fullDocument', {})
        
        message = {
            'operation': operation,
            'doc_id': str(document['_id']),
            'product': document.get('product', ''),
            'customer': document.get('customer', ''),
            'owner': document.get('owner', ''),
            'date': str(document.get('date', '')),
            'subject': document.get('subject', ''),
            'content': document.get('content', ''),  # Full content for embedding
            'timestamp': datetime.now().isoformat(),
            'stage': 'raw'
        }
        
        return message
    
    def start_monitoring(self):
        """Start monitoring MongoDB changes and send to Stage 1 Redis stream"""
        logger.info("🚀 Starting MongoDB change stream monitoring...")
        logger.info(f"📡 Sending raw documents to: {self.raw_stream}")
        
        retry_count = 0
        max_retries = 3
        
        while True:
            try:
                # Open change stream
                with self.collection.watch(full_document='updateLookup') as stream:
                    logger.info("📡 Change stream opened, listening for changes...")
                    retry_count = 0  # Reset on successful connection
                    
                    for change in stream:
                        try:
                            # Prepare raw message
                            message = self._prepare_raw_message(change)
                            
                            # Send to Stage 1 Redis stream
                            message_id = self.redis_client.xadd(
                                self.raw_stream, 
                                message,
                                maxlen=10000  # Keep last 10k messages
                            )
                            
                            logger.info(f"✅ [STAGE 1] Sent raw doc: {change['operationType']} - {message.get('doc_id')} -> {message_id}")
                            
                        except Exception as e:
                            logger.error(f"❌ Error processing change: {e}")
                            # Continue processing other changes
                            continue
                            
            except Exception as e:
                retry_count += 1
                logger.error(f"❌ Change stream error (attempt {retry_count}/{max_retries}): {e}")
                
                if retry_count >= max_retries:
                    logger.error("❌ Max retries reached, exiting...")
                    break
                
                # Exponential backoff
                sleep_time = min(60, 2 ** retry_count)
                logger.info(f"⏳ Retrying in {sleep_time} seconds...")
                time.sleep(sleep_time)

if __name__ == "__main__":
    # Configuration
    MONGO_URI = "mongodb://172.30.0.57:27017/emaildb?directConnection=true"
    REDIS_HOST = "172.30.0.57"
    REDIS_PORT = 6379
    
    # Create and start producer
    producer = MongoChangeStreamProducer(
        mongo_uri=MONGO_URI,
        redis_host=REDIS_HOST,
        redis_port=REDIS_PORT
    )
    
    try:
        producer.start_monitoring()
    except KeyboardInterrupt:
        print("\n🛑 Shutting down gracefully...")
    except Exception as e:
        print(f"❌ Fatal error: {e}")