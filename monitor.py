import redis
import requests
import time
import json
from datetime import datetime
from qdrant_client import QdrantClient

class PipelineMonitor:
    def __init__(self, redis_host, qdrant_host, embedding_host):
        self.redis_client = redis.Redis(host=redis_host, port=6379, decode_responses=True)
        self.qdrant_client = QdrantClient(host=qdrant_host, port=6333)
        self.embedding_url = f"http://{embedding_host}:8080"
        
        # Stream names
        self.stage1_stream = 'raw_document_changes'
        self.stage2_stream = 'embedded_documents'
        
    def get_redis_stats(self):
        """Get Redis streams statistics"""
        try:
            stats = {}
            
            # Stage 1 stats
            try:
                stage1_info = self.redis_client.xinfo_stream(self.stage1_stream)
                stage1_groups = self.redis_client.xinfo_groups(self.stage1_stream)
                
                stats['stage1'] = {
                    'stream_length': stage1_info['length'],
                    'total_messages': stage1_info['entries-added'],
                    'consumer_groups': len(stage1_groups),
                    'status': '✅ Active'
                }
                
                # Check pending messages for embedding processors
                if stage1_groups:
                    pending = self.redis_client.xpending(self.stage1_stream, 'embedding_processors')
                    stats['stage1']['pending_messages'] = pending['pending']
                else:
                    stats['stage1']['pending_messages'] = 0
                    
            except Exception as e:
                stats['stage1'] = {'status': f'❌ Error: {str(e)}'}
            
            # Stage 2 stats
            try:
                stage2_info = self.redis_client.xinfo_stream(self.stage2_stream)
                stage2_groups = self.redis_client.xinfo_groups(self.stage2_stream)
                
                stats['stage2'] = {
                    'stream_length': stage2_info['length'],
                    'total_messages': stage2_info['entries-added'],
                    'consumer_groups': len(stage2_groups),
                    'status': '✅ Active'
                }
                
                # Check pending messages for Qdrant upserters
                if stage2_groups:
                    pending = self.redis_client.xpending(self.stage2_stream, 'qdrant_upserters')
                    stats['stage2']['pending_messages'] = pending['pending']
                else:
                    stats['stage2']['pending_messages'] = 0
                    
            except Exception as e:
                stats['stage2'] = {'status': f'❌ Error: {str(e)}'}
                
            return stats
            
        except Exception as e:
            return {'error': f'Redis connection failed: {str(e)}'}
    
    def get_qdrant_stats(self):
        """Get Qdrant statistics"""
        try:
            collection_info = self.qdrant_client.get_collection('documents')
            return {
                'points_count': collection_info.points_count,
                'vectors_count': collection_info.vectors_count,
                'status': '✅ Active'
            }
        except Exception as e:
            return {'status': f'❌ Error: {str(e)}'}
    
    def get_embedding_service_stats(self):
        """Get embedding service statistics"""
        try:
            response = requests.get(f"{self.embedding_url}/health", timeout=5)
            if response.status_code == 200:
                health_data = response.json()
                return {
                    'status': '✅ Active',
                    'model': health_data.get('model', 'Unknown'),
                    'vector_size': health_data.get('vector_size', 'Unknown')
                }
            else:
                return {'status': f'❌ HTTP {response.status_code}'}
        except Exception as e:
            return {'status': f'❌ Error: {str(e)}'}
    
    def get_pipeline_health(self):
        """Assess overall pipeline health"""
        redis_stats = self.get_redis_stats()
        
        # Check for backlog issues
        warnings = []
        
        if 'stage1' in redis_stats and 'stream_length' in redis_stats['stage1']:
            stage1_length = redis_stats['stage1']['stream_length']
            if stage1_length > 1000:
                warnings.append(f"⚠️  Stage 1 queue backing up: {stage1_length} messages")
        
        if 'stage2' in redis_stats and 'stream_length' in redis_stats['stage2']:
            stage2_length = redis_stats['stage2']['stream_length']
            if stage2_length > 500:
                warnings.append(f"⚠️  Stage 2 queue backing up: {stage2_length} messages")
        
        # Check pending messages
        if 'stage1' in redis_stats and redis_stats['stage1'].get('pending_messages', 0) > 100:
            warnings.append(f"⚠️  Many pending Stage 1 messages: {redis_stats['stage1']['pending_messages']}")
            
        if 'stage2' in redis_stats and redis_stats['stage2'].get('pending_messages', 0) > 50:
            warnings.append(f"⚠️  Many pending Stage 2 messages: {redis_stats['stage2']['pending_messages']}")
        
        return warnings
    
    def display_dashboard(self):
        """Display real-time dashboard"""
        # Clear screen
        print("\033[2J\033[H")
        
        print("=" * 80)
        print("📊 MONGODB → REDIS STREAMS → QDRANT PIPELINE MONITOR")
        print("=" * 80)
        print(f"🕐 Last Updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print()
        
        # Get all stats
        redis_stats = self.get_redis_stats()
        qdrant_stats = self.get_qdrant_stats()
        embedding_stats = self.get_embedding_service_stats()
        warnings = self.get_pipeline_health()
        
        # Display Stage 1
        print("📥 STAGE 1: Raw Document Changes")
        print("-" * 40)
        if 'stage1' in redis_stats:
            stage1 = redis_stats['stage1']
            print(f"Status: {stage1.get('status', 'Unknown')}")
            if 'stream_length' in stage1:
                print(f"Queue Length: {stage1['stream_length']}")
                print(f"Total Processed: {stage1['total_messages']}")
                print(f"Pending Messages: {stage1['pending_messages']}")
                print(f"Consumer Groups: {stage1['consumer_groups']}")
        else:
            print("❌ Stage 1 data unavailable")
        print()
        
        # Display Embedding Service
        print("🧠 EMBEDDING SERVICE")
        print("-" * 40)
        print(f"Status: {embedding_stats.get('status', 'Unknown')}")
        if 'model' in embedding_stats:
            print(f"Model: {embedding_stats['model']}")
            print(f"Vector Size: {embedding_stats['vector_size']}")
        print()
        
        # Display Stage 2
        print("📤 STAGE 2: Embedded Documents")
        print("-" * 40)
        if 'stage2' in redis_stats:
            stage2 = redis_stats['stage2']
            print(f"Status: {stage2.get('status', 'Unknown')}")
            if 'stream_length' in stage2:
                print(f"Queue Length: {stage2['stream_length']}")
                print(f"Total Processed: {stage2['total_messages']}")
                print(f"Pending Messages: {stage2['pending_messages']}")
                print(f"Consumer Groups: {stage2['consumer_groups']}")
        else:
            print("❌ Stage 2 data unavailable")
        print()
        
        # Display Qdrant
        print("🎯 QDRANT VECTOR DATABASE")
        print("-" * 40)
        print(f"Status: {qdrant_stats.get('status', 'Unknown')}")
        if 'points_count' in qdrant_stats:
            print(f"Points Count: {qdrant_stats['points_count']}")
            print(f"Vectors Count: {qdrant_stats['vectors_count']}")
        print()
        
        # Display warnings
        if warnings:
            print("⚠️  ALERTS")
            print("-" * 40)
            for warning in warnings:
                print(warning)
            print()
        else:
            print("✅ ALL SYSTEMS HEALTHY")
            print()
        
        # Calculate throughput (approximate)
        if ('stage1' in redis_stats and 'stage2' in redis_stats and 
            'total_messages' in redis_stats['stage1'] and 'total_messages' in redis_stats['stage2']):
            
            stage1_total = redis_stats['stage1']['total_messages']
            stage2_total = redis_stats['stage2']['total_messages']
            
            print("📈 THROUGHPUT")
            print("-" * 40)
            print(f"Documents Received: {stage1_total}")
            print(f"Documents Embedded: {stage2_total}")
            
            if stage1_total > 0:
                embedding_completion = (stage2_total / stage1_total) * 100
                print(f"Embedding Progress: {embedding_completion:.1f}%")
        
        print()
        print("Press Ctrl+C to stop monitoring...")
    
    def run_monitoring(self, refresh_interval=10):
        """Run continuous monitoring"""
        try:
            while True:
                self.display_dashboard()
                time.sleep(refresh_interval)
        except KeyboardInterrupt:
            print("\n\n🛑 Monitoring stopped.")

def main():
    # Configuration
    REDIS_HOST = "172.30.0.57"
    QDRANT_HOST = "172.30.0.57" 
    EMBEDDING_HOST = "172.30.0.59"
    
    print("🚀 Starting Pipeline Monitor...")
    print("📡 Connecting to services...")
    
    monitor = PipelineMonitor(
        redis_host=REDIS_HOST,
        qdrant_host=QDRANT_HOST,
        embedding_host=EMBEDDING_HOST
    )
    
    # Run monitoring with 10-second refresh
    monitor.run_monitoring(refresh_interval=10)

if __name__ == "__main__":
    main()