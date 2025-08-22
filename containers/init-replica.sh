#!/bin/bash

docker exec kb_mongodb mongosh --eval "
try {
  const status = rs.status();
  console.log('[GOOD] Replica set already initialized');
  console.log('Current status:', status.set);
} catch(e) {
  console.log('[INFO] Initializing replica set rs0');
  const result = rs.initiate({
    _id: 'rs0',
    members: [
      { 
        _id: 0, 
        host: 'kb_mongodb:27017',
        priority: 1
      }
    ]
  });
  if (result.ok === 1) {
    console.log('[GOOD] Replica set initialized successfully');
  } else {
    console.log('[INFO] Failed to initialize replica set:', result);
  }
}
"
