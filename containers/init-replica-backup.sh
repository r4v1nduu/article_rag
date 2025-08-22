#!/bin/bash

PRIMARY_SERVER_IP="YOUR_PRIMARY_SERVER_IP"
SECONDARY_SERVER_IP="YOUR_SECONDARY_SERVER_IP"

docker exec kb_mongodb mongosh --eval "
try {
  const status = rs.status();
  console.log('[GOOD] Replica set already initialized');
  console.log('Current members:', status.members.length);
  const hasSecondary = status.members.some(m => m.name.includes('$SECONDARY_SERVER_IP'));
  if (!hasSecondary && status.members.length === 1) {
    console.log('[INFO] Adding secondary server to replica set');
    rs.add('$SECONDARY_SERVER_IP:27017');
    console.log('[GOOD] Secondary server added to replica set');
  }
} catch(e) {
  console.log('[INFO] Initializing replica set with primary and secondary...');
  const result = rs.initiate({
    _id: 'rs0',
    members: [
      { 
        _id: 0, 
        host: '$PRIMARY_SERVER_IP:27017',
        priority: 2,
        votes: 1
      },
      { 
        _id: 1, 
        host: '$SECONDARY_SERVER_IP:27017',
        priority: 1,
        votes: 1
      }
    ]
  });
  if (result.ok === 1) {
    console.log('[GOOD] Replica set initialized with primary and secondary');
  } else {
    console.log('[BAD] Failed to initialize replica set:', result);
  }
}
"

