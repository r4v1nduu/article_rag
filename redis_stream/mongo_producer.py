import os
import time
import logging
from pymongo import MongoClient
import redis
from datetime import datetime
from dotenv import load_dotenv
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

MONGO_URI = os.getenv("MONGO_URI")
MONGO_DB = os.getenv("MONGO_DB")
MONGO_COLLECTION = os.getenv("MONGO_COLLECTION")
REDIS_HOST = os.getenv("REDIS_HOST")
REDIS_PORT = os.getenv("REDIS_PORT")

class MongoChangeStreamProducer:
    def __init__(self, mongo_uri, mongo_db, mongo_collection, redis_host, redis_port, redis_db=0):
        
        # MongoDB connection
        self.mongo_client = MongoClient(mongo_uri)
        self.db = self.mongo_client[mongo_db]
        self.collection = self.db[mongo_collection] 

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
            logger.info("[INFO] MongoDB connected successfully")

            # Test Redis
            self.redis_client.ping()
            logger.info("[INFO] Redis connected successfully")

        except Exception as e:
            logger.error(f"[ERROR] Connection failed: {e}")
            raise
    
    # Prepare raw document message for Stage 1 stream
    def _prepare_raw_message(self, change_event):

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
            'content': document.get('body', ''),
            'timestamp': datetime.now().isoformat(),
            'stage': 'raw'
        }
        
        return message
    
    # Start monitoring MongoDB changes and send to Stage 1 Redis stream
    def start_monitoring(self):

        logger.info("[INFO] Starting MongoDB change stream monitoring")
        logger.info(f"[INFO] Sending raw documents to: {self.raw_stream}")

        retry_count = 0
        max_retries = 3
        
        while True:
            try:
                # Open change stream
                with self.collection.watch(full_document='updateLookup') as stream:
                    logger.info("[INFO] Change stream opened, listening for changes")
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

                            logger.info(f"[INFO] Sent raw doc: {change['operationType']} - {message.get('doc_id')} -> {message_id}")

                        except Exception as e:
                            logger.error(f"[ERROR] Error processing change: {e}")
                            # Continue processing other changes
                            continue
                            
            except Exception as e:
                retry_count += 1
                logger.error(f"[ERROR] Change stream error (attempt {retry_count}/{max_retries}): {e}")

                if retry_count >= max_retries:
                    logger.error("[ERROR] Max retries reached, exiting")
                    break
                
                # Exponential backoff
                sleep_time = min(60, 2 ** retry_count)
                logger.info(f"[INFO] Retrying in {sleep_time} seconds")
                time.sleep(sleep_time)

if __name__ == "__main__":

    # Create and start producer
    producer = MongoChangeStreamProducer(
        mongo_uri=MONGO_URI,
        mongo_db=MONGO_DB,
        mongo_collection=MONGO_COLLECTION,
        redis_host=REDIS_HOST,
        redis_port=REDIS_PORT
    )
    
    try:
        producer.start_monitoring()
    except KeyboardInterrupt:
        print("\n[INFO] Shutting down gracefully")
    except Exception as e:
        print(f"[ERROR] Fatal error: {e}")
