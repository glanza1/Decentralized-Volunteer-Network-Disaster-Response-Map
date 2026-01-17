"""
p2p.py - P2P Networking Layer for Decentralized Disaster Response System

This module implements REAL P2P networking using sockets.
It provides gossip-based publish/subscribe for message dissemination.

Architecture:
- TCP server for receiving messages from peers
- TCP client for sending messages to peers  
- UDP broadcast for local network peer discovery
- Gossip protocol for message propagation
"""

import asyncio
import logging
import json
import socket
from typing import Dict, Set, Callable, Optional, List
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum

from models import HelpRequest, NodeIdentity, PeerInfo
from storage import message_storage

# BLE support (optional)
try:
    from ble import BLENode, BLEMessage, init_ble_node, get_ble_node, stop_ble_node
    BLE_AVAILABLE = True
except ImportError:
    BLE_AVAILABLE = False

logger = logging.getLogger(__name__)

# Configuration
UDP_DISCOVERY_PORT = 5000
MESSAGE_BUFFER_SIZE = 65535


class GossipTopic(str, Enum):
    """Topics for the gossip pub/sub system."""
    HELP_REQUESTS = "disaster/help-requests"
    PEER_DISCOVERY = "disaster/peer-discovery"
    HEARTBEAT = "disaster/heartbeat"


@dataclass
class GossipMessage:
    """Wrapper for messages in the gossip protocol."""
    topic: str
    payload: dict
    sender_id: str
    message_id: str
    timestamp: float = field(default_factory=lambda: datetime.utcnow().timestamp())
    
    def to_json(self) -> str:
        return json.dumps({
            "topic": self.topic,
            "payload": self.payload,
            "sender_id": self.sender_id,
            "message_id": self.message_id,
            "timestamp": self.timestamp
        })
    
    @classmethod
    def from_json(cls, data: str) -> 'GossipMessage':
        d = json.loads(data)
        return cls(
            topic=d["topic"],
            payload=d["payload"],
            sender_id=d["sender_id"],
            message_id=d["message_id"],
            timestamp=d.get("timestamp", datetime.utcnow().timestamp())
        )


class P2PNode:
    """
    A P2P node implementation using REAL socket-based networking.
    
    Features:
    - TCP server for receiving messages
    - TCP client for sending to peers
    - UDP broadcast for peer discovery on local network
    - Gossip protocol for message propagation
    """
    
    def __init__(
        self,
        identity: Optional[NodeIdentity] = None,
        listen_port: int = 4001,
        bootstrap_peers: Optional[List[str]] = None,
        enable_ble: bool = False
    ):
        """Initialize the P2P node."""
        self.identity = identity or NodeIdentity.generate_conceptual()
        self.listen_port = listen_port
        self.bootstrap_peers = bootstrap_peers or []
        self.enable_ble = enable_ble and BLE_AVAILABLE
        
        # BLE node reference
        self._ble_node: Optional[BLENode] = None
        
        # Peer management
        self._peers: Dict[str, PeerInfo] = {}
        self._connected_peers: Set[str] = set()
        self._peer_writers: Dict[str, asyncio.StreamWriter] = {}
        
        # Pub/Sub state
        self._subscriptions: Dict[str, List[Callable]] = {}
        self._seen_messages: Set[str] = set()
        
        # Statistics
        self._start_time = datetime.utcnow()
        self._messages_sent = 0
        self._messages_received = 0
        
        # Server state
        self._server: Optional[asyncio.Server] = None
        self._running = False
        self._tasks: List[asyncio.Task] = []
        
        logger.info(f"P2P Node initialized: {self.identity.node_id}")
    
    async def start(self) -> None:
        """Start the P2P node with real networking."""
        self._running = True
        
        # Start TCP server for incoming connections
        self._server = await asyncio.start_server(
            self._handle_peer_connection,
            '0.0.0.0',
            self.listen_port
        )
        
        logger.info(f"TCP server listening on port {self.listen_port}")
        
        # Start background tasks
        self._tasks = [
            asyncio.create_task(self._udp_discovery_listener()),
            asyncio.create_task(self._discovery_broadcast_loop()),
            asyncio.create_task(self._heartbeat_loop()),
            asyncio.create_task(self._cleanup_loop()),
            asyncio.create_task(self._server.serve_forever()),
        ]
        
        # Connect to bootstrap peers
        for peer_addr in self.bootstrap_peers:
            asyncio.create_task(self._connect_to_peer(peer_addr))
        
        # Start BLE node if enabled
        if self.enable_ble:
            await self._start_ble()
        
        logger.info(f"P2P node started: {self.identity.display_name} (BLE: {self.enable_ble})")
    
    async def stop(self) -> None:
        """Stop the P2P node."""
        self._running = False
        
        # Close peer connections
        for writer in self._peer_writers.values():
            writer.close()
            try:
                await writer.wait_closed()
            except:
                pass
        self._peer_writers.clear()
        
        # Stop server
        if self._server:
            self._server.close()
            await self._server.wait_closed()
        
        # Cancel tasks
        for task in self._tasks:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        
        self._tasks.clear()
        logger.info("P2P node stopped")
    
    async def _handle_peer_connection(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        """Handle incoming TCP connection from a peer."""
        peer_addr = writer.get_extra_info('peername')
        logger.info(f"New peer connection from {peer_addr}")
        
        try:
            while self._running:
                # Read message length prefix (4 bytes)
                length_data = await reader.read(4)
                if not length_data:
                    break
                
                msg_length = int.from_bytes(length_data, 'big')
                if msg_length > MESSAGE_BUFFER_SIZE:
                    logger.warning(f"Message too large: {msg_length}")
                    break
                
                # Read the message
                msg_data = await reader.read(msg_length)
                if not msg_data:
                    break
                
                try:
                    message = GossipMessage.from_json(msg_data.decode('utf-8'))
                    await self._handle_incoming_message(message)
                except json.JSONDecodeError as e:
                    logger.error(f"Invalid message JSON: {e}")
                    
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Peer connection error: {e}")
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except:
                pass
            logger.info(f"Peer disconnected: {peer_addr}")
    
    async def _connect_to_peer(self, peer_addr: str) -> bool:
        """Connect to a peer via TCP."""
        try:
            # Parse address (format: "host:port" or "host:port/node_id")
            parts = peer_addr.split("/")
            addr_part = parts[0]
            peer_id = parts[1] if len(parts) > 1 else addr_part
            
            if ":" in addr_part:
                host, port_str = addr_part.split(":")
                port = int(port_str)
            else:
                host = addr_part
                port = 4001
            
            logger.info(f"Connecting to peer at {host}:{port}")
            
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(host, port),
                timeout=5.0
            )
            
            # Store connection
            self._peer_writers[peer_id] = writer
            self._connected_peers.add(peer_id)
            self._peers[peer_id] = PeerInfo(
                node_id=peer_id,
                multiaddr=peer_addr,
                last_seen=datetime.utcnow()
            )
            
            # Start reading from this peer
            asyncio.create_task(self._read_from_peer(peer_id, reader, writer))
            
            logger.info(f"Connected to peer: {peer_id}")
            return True
            
        except asyncio.TimeoutError:
            logger.warning(f"Connection timeout to {peer_addr}")
            return False
        except Exception as e:
            logger.error(f"Failed to connect to {peer_addr}: {e}")
            return False
    
    async def _read_from_peer(self, peer_id: str, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        """Read messages from a connected peer."""
        try:
            while self._running and peer_id in self._connected_peers:
                length_data = await reader.read(4)
                if not length_data:
                    break
                
                msg_length = int.from_bytes(length_data, 'big')
                msg_data = await reader.read(msg_length)
                if not msg_data:
                    break
                
                try:
                    message = GossipMessage.from_json(msg_data.decode('utf-8'))
                    await self._handle_incoming_message(message)
                except:
                    pass
                    
        except:
            pass
        finally:
            self._disconnect_peer(peer_id)
    
    def _disconnect_peer(self, peer_id: str) -> None:
        """Clean up peer connection."""
        self._connected_peers.discard(peer_id)
        if peer_id in self._peer_writers:
            try:
                self._peer_writers[peer_id].close()
            except:
                pass
            del self._peer_writers[peer_id]
        if peer_id in self._peers:
            del self._peers[peer_id]
        logger.info(f"Disconnected peer: {peer_id}")
    
    def subscribe(self, topic: str, handler: Callable[[dict], None]) -> None:
        """Subscribe to a gossip topic."""
        if topic not in self._subscriptions:
            self._subscriptions[topic] = []
        self._subscriptions[topic].append(handler)
        logger.info(f"Subscribed to topic: {topic}")
    
    async def publish(self, topic: str, payload: dict) -> None:
        """Publish a message to all connected peers."""
        message = GossipMessage(
            topic=topic,
            payload=payload,
            sender_id=self.identity.node_id,
            message_id=payload.get("id", f"{self.identity.node_id}-{datetime.utcnow().timestamp()}")
        )
        
        # Mark as seen to prevent echo
        self._seen_messages.add(message.message_id)
        
        # Send to all connected peers (TCP)
        await self._broadcast(message)
        
        # Also broadcast over BLE if enabled
        if self._ble_node:
            try:
                await self._ble_node.broadcast(topic, payload)
            except Exception as e:
                logger.warning(f"BLE broadcast failed: {e}")
        
        self._messages_sent += 1
        logger.info(f"Published message to {topic}: {message.message_id}")
    
    async def _broadcast(self, message: GossipMessage) -> None:
        """Broadcast a message to all connected peers via TCP."""
        msg_bytes = message.to_json().encode('utf-8')
        length_prefix = len(msg_bytes).to_bytes(4, 'big')
        data = length_prefix + msg_bytes
        
        disconnected = []
        
        for peer_id, writer in self._peer_writers.items():
            try:
                writer.write(data)
                await writer.drain()
            except Exception as e:
                logger.warning(f"Failed to send to {peer_id}: {e}")
                disconnected.append(peer_id)
        
        # Clean up failed connections
        for peer_id in disconnected:
            self._disconnect_peer(peer_id)
    
    async def _handle_incoming_message(self, message: GossipMessage) -> None:
        """Handle an incoming gossip message."""
        # Deduplicate
        if message.message_id in self._seen_messages:
            return
        self._seen_messages.add(message.message_id)
        
        # Limit seen messages cache
        if len(self._seen_messages) > 10000:
            self._seen_messages = set(list(self._seen_messages)[-5000:])
        
        self._messages_received += 1
        
        # Update peer last seen
        if message.sender_id in self._peers:
            self._peers[message.sender_id].last_seen = datetime.utcnow()
        
        # Deliver to local subscribers
        if message.topic in self._subscriptions:
            for handler in self._subscriptions[message.topic]:
                try:
                    handler(message.payload)
                except Exception as e:
                    logger.error(f"Handler error: {e}")
        
        # Gossip: forward to other peers (except sender)
        for peer_id, writer in list(self._peer_writers.items()):
            if peer_id != message.sender_id:
                try:
                    msg_bytes = message.to_json().encode('utf-8')
                    length_prefix = len(msg_bytes).to_bytes(4, 'big')
                    writer.write(length_prefix + msg_bytes)
                    await writer.drain()
                except:
                    pass
    
    async def _udp_discovery_listener(self) -> None:
        """Listen for UDP discovery broadcasts from other nodes."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.setblocking(False)
        
        try:
            sock.bind(('', UDP_DISCOVERY_PORT))
            logger.info(f"UDP discovery listening on port {UDP_DISCOVERY_PORT}")
            
            loop = asyncio.get_event_loop()
            
            while self._running:
                try:
                    data, addr = await loop.sock_recvfrom(sock, 1024)
                    msg = json.loads(data.decode('utf-8'))
                    
                    # Ignore our own broadcasts
                    if msg.get("node_id") == self.identity.node_id:
                        continue
                    
                    peer_addr = f"{addr[0]}:{msg.get('port', 4001)}"
                    peer_id = msg.get("node_id", peer_addr)
                    
                    # Connect if not already connected
                    if peer_id not in self._connected_peers:
                        logger.info(f"Discovered peer via UDP: {peer_addr}")
                        asyncio.create_task(self._connect_to_peer(peer_addr + "/" + peer_id))
                        
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    await asyncio.sleep(1)
                    
        except Exception as e:
            logger.error(f"UDP listener error: {e}")
        finally:
            sock.close()
    
    async def _discovery_broadcast_loop(self) -> None:
        """Periodically broadcast our presence via UDP."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.setblocking(False)
        
        try:
            while self._running:
                try:
                    msg = json.dumps({
                        "node_id": self.identity.node_id,
                        "port": self.listen_port,
                        "name": self.identity.display_name
                    }).encode('utf-8')
                    
                    # Broadcast to local network
                    sock.sendto(msg, ('<broadcast>', UDP_DISCOVERY_PORT))
                    
                except Exception as e:
                    logger.debug(f"Broadcast error: {e}")
                
                await asyncio.sleep(10)  # Broadcast every 10 seconds
                
        except asyncio.CancelledError:
            pass
        finally:
            sock.close()
    
    async def _heartbeat_loop(self) -> None:
        """Send periodic heartbeats to maintain connections."""
        while self._running:
            try:
                await asyncio.sleep(60)
                
                if self._connected_peers:
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
        """Periodically clean up stale data."""
        while self._running:
            try:
                await asyncio.sleep(300)
                
                cleaned = message_storage.cleanup_expired()
                if cleaned > 0:
                    logger.info(f"Cleaned up {cleaned} expired messages")
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Cleanup error: {e}")
    
    def get_stats(self) -> dict:
        """Get P2P node statistics."""
        uptime = (datetime.utcnow() - self._start_time).total_seconds()
        stats = {
            "node_id": self.identity.node_id,
            "display_name": self.identity.display_name,
            "uptime_seconds": uptime,
            "connected_peers": len(self._connected_peers),
            "known_peers": len(self._peers),
            "messages_sent": self._messages_sent,
            "messages_received": self._messages_received,
            "subscriptions": list(self._subscriptions.keys()),
            "ble_enabled": self.enable_ble
        }
        
        # Add BLE stats if available
        if self._ble_node:
            stats["ble"] = self._ble_node.get_stats()
        
        return stats
    
    def get_peers(self) -> List[PeerInfo]:
        """Get list of connected peers."""
        return list(self._peers.values())
    
    async def _start_ble(self) -> None:
        """Start the BLE node for Bluetooth communication."""
        try:
            def on_ble_message(message: BLEMessage):
                """Handle incoming BLE message."""
                # Convert to gossip format and process
                if message.topic in self._subscriptions:
                    for handler in self._subscriptions[message.topic]:
                        try:
                            handler(message.payload)
                        except Exception as e:
                            logger.error(f"BLE message handler error: {e}")
            
            self._ble_node = await init_ble_node(
                node_id=self.identity.node_id,
                node_name=self.identity.display_name or "DisasterNode",
                on_message=on_ble_message
            )
            logger.info("BLE node started successfully")
            
        except Exception as e:
            logger.error(f"Failed to start BLE node: {e}")
            self.enable_ble = False
            self._ble_node = None
    
    async def _stop_ble(self) -> None:
        """Stop the BLE node."""
        if self._ble_node:
            await self._ble_node.stop()
            self._ble_node = None


# Global P2P node instance
p2p_node: Optional[P2PNode] = None


def get_p2p_node() -> P2PNode:
    """Get the global P2P node instance."""
    if p2p_node is None:
        raise RuntimeError("P2P node not initialized")
    return p2p_node


def init_p2p_node(
    identity: Optional[NodeIdentity] = None,
    listen_port: int = 4001,
    bootstrap_peers: Optional[List[str]] = None,
    enable_ble: bool = False
) -> P2PNode:
    """Initialize the global P2P node instance."""
    global p2p_node
    p2p_node = P2PNode(
        identity=identity,
        listen_port=listen_port,
        bootstrap_peers=bootstrap_peers,
        enable_ble=enable_ble
    )
    return p2p_node
