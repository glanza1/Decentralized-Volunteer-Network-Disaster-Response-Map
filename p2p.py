"""
p2p.py - P2P Networking Layer for Decentralized Disaster Response System

This module implements a conceptual P2P networking layer based on libp2p principles.
It provides gossip-based publish/subscribe for message dissemination.

Architecture Overview:
- Each node maintains connections to multiple peers
- Messages propagate via gossip protocol (epidemic broadcast)
- Subscription model allows filtering by topic
- UUID-based deduplication prevents message storms

libp2p Integration Notes:
In production, this would use py-libp2p with:
- Noise protocol for encrypted connections
- mDNS for local peer discovery
- DHT (Kademlia) for distributed peer routing
- GossipSub for efficient pub/sub

Offline/Mesh Networking Concepts:
=========================================
This implementation is designed to conceptually support offline/mesh scenarios:

1. Bluetooth Low Energy (BLE):
   - Nodes advertise using BLE beacons
   - Message exchange via GATT characteristics
   - Limited bandwidth (~1Mbps) suits our JSON messages
   - Range: ~100m outdoors
   
2. Wi-Fi Direct:
   - Forms ad-hoc networks without infrastructure
   - Higher bandwidth (~250Mbps)
   - Automatic group formation
   - Range: ~200m
   
3. Hybrid Approach:
   - Use BLE for discovery and small messages
   - Upgrade to Wi-Fi Direct for bulk sync
   - Seamlessly switch between transport layers
   
4. Store-and-Forward:
   - Messages queue when no peers available
   - Sync occurs when devices come into range
   - TTL prevents stale message accumulation
   - Hop count limits propagation diameter
"""

import asyncio
import logging
import json
from typing import Dict, Set, Callable, Optional, List
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum

from models import HelpRequest, NodeIdentity, PeerInfo
from storage import message_storage

logger = logging.getLogger(__name__)


class GossipTopic(str, Enum):
    """Topics for the gossip pub/sub system."""
    HELP_REQUESTS = "disaster/help-requests"
    PEER_DISCOVERY = "disaster/peer-discovery"
    HEARTBEAT = "disaster/heartbeat"


@dataclass
class GossipMessage:
    """
    Wrapper for messages in the gossip protocol.
    
    The gossip protocol wraps application messages with
    metadata for routing and deduplication.
    """
    topic: str
    payload: dict
    sender_id: str
    message_id: str
    timestamp: float = field(default_factory=lambda: datetime.utcnow().timestamp())


class P2PNode:
    """
    A P2P node implementation using gossip-based pub/sub.
    
    This is a conceptual implementation that simulates P2P networking.
    In production, this would integrate with py-libp2p.
    
    Key Concepts:
    - Each node is both a client and server (peer)
    - Messages propagate via gossip (epidemic broadcast)
    - Subscriptions filter incoming messages by topic
    - Peer connections are maintained in the background
    
    Gossip Protocol Properties:
    - Probabilistic delivery (high reliability)
    - Logarithmic message complexity
    - Resilient to node failures
    - Eventually consistent message delivery
    """
    
    def __init__(
        self,
        identity: Optional[NodeIdentity] = None,
        listen_port: int = 4001,
        bootstrap_peers: Optional[List[str]] = None
    ):
        """
        Initialize the P2P node.
        
        Args:
            identity: Node's cryptographic identity. Generated if not provided.
            listen_port: Port to listen for incoming connections.
            bootstrap_peers: Initial peers to connect to (multiaddrs).
        """
        self.identity = identity or NodeIdentity.generate_conceptual()
        self.listen_port = listen_port
        self.bootstrap_peers = bootstrap_peers or []
        
        # Peer management
        self._peers: Dict[str, PeerInfo] = {}
        self._connected_peers: Set[str] = set()
        
        # Pub/Sub state
        self._subscriptions: Dict[str, List[Callable]] = {}
        self._message_handlers: Dict[str, Callable] = {}
        
        # Statistics
        self._start_time = datetime.utcnow()
        self._messages_sent = 0
        self._messages_received = 0
        
        # Background tasks
        self._running = False
        self._tasks: List[asyncio.Task] = []
        
        logger.info(f"P2P Node initialized: {self.identity.node_id}")
    
    async def start(self) -> None:
        """
        Start the P2P node.
        
        This initiates:
        1. Listener for incoming connections
        2. Bootstrap peer connections
        3. Peer discovery via mDNS (simulated)
        4. Heartbeat broadcasting
        5. Message cleanup task
        """
        self._running = True
        
        logger.info(f"Starting P2P node on port {self.listen_port}")
        
        # Start background tasks
        self._tasks = [
            asyncio.create_task(self._discovery_loop()),
            asyncio.create_task(self._heartbeat_loop()),
            asyncio.create_task(self._cleanup_loop()),
        ]
        
        # Connect to bootstrap peers
        for peer_addr in self.bootstrap_peers:
            await self._connect_to_peer(peer_addr)
        
        logger.info(f"P2P node started: {self.identity.display_name}")
    
    async def stop(self) -> None:
        """Stop the P2P node and cleanup resources."""
        self._running = False
        
        # Cancel background tasks
        for task in self._tasks:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        
        self._tasks.clear()
        logger.info("P2P node stopped")
    
    def subscribe(self, topic: str, handler: Callable[[dict], None]) -> None:
        """
        Subscribe to a gossip topic.
        
        Args:
            topic: Topic to subscribe to (e.g., GossipTopic.HELP_REQUESTS)
            handler: Callback function for received messages.
        
        The handler receives the message payload (dict).
        """
        if topic not in self._subscriptions:
            self._subscriptions[topic] = []
        
        self._subscriptions[topic].append(handler)
        logger.info(f"Subscribed to topic: {topic}")
    
    async def publish(self, topic: str, payload: dict) -> None:
        """
        Publish a message to a gossip topic.
        
        Args:
            topic: Topic to publish to.
            payload: Message payload (must be JSON-serializable).
        
        The message is wrapped in a GossipMessage and broadcast to all peers.
        Peers will forward it to their peers (gossip propagation).
        """
        message = GossipMessage(
            topic=topic,
            payload=payload,
            sender_id=self.identity.node_id,
            message_id=payload.get("id", str(id(payload)))
        )
        
        # Broadcast to all connected peers
        await self._broadcast(message)
        
        self._messages_sent += 1
        logger.info(f"Published message to {topic}: {message.message_id}")
    
    async def _broadcast(self, message: GossipMessage) -> None:
        """
        Broadcast a message to all connected peers.
        
        In production libp2p, this would:
        1. Serialize the message
        2. Send to each connected peer's stream
        3. Peers would forward based on their subscriptions
        
        Gossip optimization strategies:
        - Lazy push: Send message IDs first, full message on request
        - Eager push: Immediately send full messages
        - Hybrid: Use eager for high-priority, lazy for others
        """
        # Simulate network broadcast (conceptual)
        for peer_id in self._connected_peers:
            await self._send_to_peer(peer_id, message)
    
    async def _send_to_peer(self, peer_id: str, message: GossipMessage) -> bool:
        """
        Send a message to a specific peer.
        
        In production, this would:
        1. Get the peer's connection/stream
        2. Serialize and encrypt the message
        3. Send over the network
        4. Handle acknowledgment or retry
        """
        # Simulated send (would be actual network I/O in production)
        logger.debug(f"Sending message to peer {peer_id}: {message.message_id}")
        
        # Simulate network latency
        await asyncio.sleep(0.01)
        
        return True
    
    async def _handle_incoming_message(self, message: GossipMessage) -> None:
        """
        Handle an incoming gossip message.
        
        This is called when we receive a message from a peer.
        The message is:
        1. Checked for duplicates
        2. Delivered to local subscribers
        3. Forwarded to other peers (gossip propagation)
        """
        # Check if we've already seen this message
        if message_storage.has_seen(message.message_id):
            logger.debug(f"Duplicate message ignored: {message.message_id}")
            return
        
        self._messages_received += 1
        
        # Deliver to local subscribers
        if message.topic in self._subscriptions:
            for handler in self._subscriptions[message.topic]:
                try:
                    handler(message.payload)
                except Exception as e:
                    logger.error(f"Handler error: {e}")
        
        # Forward to other peers (gossip propagation)
        # Don't forward back to sender
        for peer_id in self._connected_peers:
            if peer_id != message.sender_id:
                await self._send_to_peer(peer_id, message)
    
    async def _connect_to_peer(self, multiaddr: str) -> bool:
        """
        Connect to a peer using their multiaddress.
        
        libp2p multiaddresses encode transport and identity:
        - /ip4/192.168.1.1/tcp/4001/p2p/QmNodeId
        - /dns4/example.com/tcp/4001/p2p/QmNodeId
        
        For mesh networks:
        - /bluetooth/AA:BB:CC:DD:EE:FF/p2p/NodeId
        - /wifi-direct/DIRECT-xy-DeviceName/p2p/NodeId
        """
        logger.info(f"Connecting to peer: {multiaddr}")
        
        # Parse multiaddr and extract peer ID (simplified)
        peer_id = multiaddr.split("/")[-1] if "/" in multiaddr else multiaddr
        
        # Simulate connection establishment
        await asyncio.sleep(0.1)
        
        # Add to connected peers
        self._connected_peers.add(peer_id)
        self._peers[peer_id] = PeerInfo(
            node_id=peer_id,
            multiaddr=multiaddr,
            last_seen=datetime.utcnow()
        )
        
        logger.info(f"Connected to peer: {peer_id}")
        return True
    
    async def _discovery_loop(self) -> None:
        """
        Background task for peer discovery.
        
        In production, this would use:
        1. mDNS for local network discovery
        2. DHT for global peer routing
        3. Bootstrap nodes for initial connection
        
        For offline/mesh:
        - BLE scanning for nearby devices
        - Wi-Fi Direct service discovery
        - NFC tap for quick pairing
        """
        while self._running:
            try:
                # Simulate periodic discovery
                await asyncio.sleep(30)  # Check every 30 seconds
                
                # In production: query mDNS, DHT, scan BLE, etc.
                logger.debug("Running peer discovery...")
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Discovery error: {e}")
    
    async def _heartbeat_loop(self) -> None:
        """
        Background task for heartbeat broadcasting.
        
        Heartbeats serve multiple purposes:
        1. Keep connections alive
        2. Share node state/capabilities
        3. Detect peer failures
        4. Maintain peer list freshness
        """
        while self._running:
            try:
                await asyncio.sleep(60)  # Heartbeat every 60 seconds
                
                # Broadcast heartbeat
                heartbeat = {
                    "node_id": self.identity.node_id,
                    "timestamp": datetime.utcnow().isoformat(),
                    "peers_count": len(self._connected_peers),
                    "messages_count": message_storage.get_stats()["total_stored"]
                }
                
                await self.publish(GossipTopic.HEARTBEAT, heartbeat)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Heartbeat error: {e}")
    
    async def _cleanup_loop(self) -> None:
        """
        Background task for cleaning up stale data.
        
        Periodically:
        1. Remove expired messages
        2. Prune inactive peers
        3. Compact seen message IDs
        """
        while self._running:
            try:
                await asyncio.sleep(300)  # Cleanup every 5 minutes
                
                # Cleanup expired messages
                cleaned = message_storage.cleanup_expired()
                if cleaned > 0:
                    logger.info(f"Cleaned up {cleaned} expired messages")
                
                # Prune stale peers (not seen in 5 minutes)
                cutoff = datetime.utcnow()
                stale_peers = [
                    peer_id for peer_id, peer in self._peers.items()
                    if (cutoff - peer.last_seen).total_seconds() > 300
                ]
                
                for peer_id in stale_peers:
                    self._connected_peers.discard(peer_id)
                    del self._peers[peer_id]
                    logger.info(f"Pruned stale peer: {peer_id}")
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Cleanup error: {e}")
    
    def get_stats(self) -> dict:
        """Get P2P node statistics."""
        uptime = (datetime.utcnow() - self._start_time).total_seconds()
        return {
            "node_id": self.identity.node_id,
            "display_name": self.identity.display_name,
            "uptime_seconds": uptime,
            "connected_peers": len(self._connected_peers),
            "known_peers": len(self._peers),
            "messages_sent": self._messages_sent,
            "messages_received": self._messages_received,
            "subscriptions": list(self._subscriptions.keys())
        }
    
    def get_peers(self) -> List[PeerInfo]:
        """Get list of known peers."""
        return list(self._peers.values())


# Simulated incoming message handler for testing/demo purposes
async def simulate_incoming_message(node: P2PNode, message: HelpRequest) -> None:
    """
    Simulate receiving a message from the network.
    
    This is used for testing and demonstration.
    In production, messages would arrive via actual network connections.
    """
    gossip_msg = GossipMessage(
        topic=GossipTopic.HELP_REQUESTS,
        payload=message.to_gossip_message(),
        sender_id=message.sender_id,
        message_id=message.id
    )
    
    await node._handle_incoming_message(gossip_msg)


# Global P2P node instance (initialized in main.py)
p2p_node: Optional[P2PNode] = None


def get_p2p_node() -> P2PNode:
    """Get the global P2P node instance."""
    if p2p_node is None:
        raise RuntimeError("P2P node not initialized")
    return p2p_node


def init_p2p_node(
    identity: Optional[NodeIdentity] = None,
    listen_port: int = 4001,
    bootstrap_peers: Optional[List[str]] = None
) -> P2PNode:
    """Initialize the global P2P node instance."""
    global p2p_node
    p2p_node = P2PNode(
        identity=identity,
        listen_port=listen_port,
        bootstrap_peers=bootstrap_peers
    )
    return p2p_node
