"""
models.py - Data Models for Decentralized Disaster Response System

This module defines the core data structures used throughout the P2P network.
All messages are JSON-serializable and include cryptographic identity support.

In an offline/mesh scenario (Bluetooth/Wi-Fi Direct):
- These same models would be serialized and transmitted over local radio links
- The compact JSON format is ideal for low-bandwidth mesh networks
- UUID-based deduplication works regardless of transport layer
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from uuid import uuid4
from enum import Enum


class RequestPriority(str, Enum):
    """Priority levels for help requests in disaster scenarios."""
    CRITICAL = "critical"      # Life-threatening situations
    HIGH = "high"              # Urgent medical/rescue needs
    MEDIUM = "medium"          # Important but not immediate
    LOW = "low"                # General assistance requests


class RequestType(str, Enum):
    """Types of help requests that can be broadcast."""
    MEDICAL = "medical"        # Medical emergency
    RESCUE = "rescue"          # Trapped/stranded persons
    SHELTER = "shelter"        # Need for shelter
    FOOD_WATER = "food_water"  # Basic supplies needed
    TRANSPORT = "transport"    # Evacuation assistance
    INFO = "info"              # Information request


class GeoLocation(BaseModel):
    """
    Geographic coordinates for locating help requests.
    
    In mesh networks, this enables location-based routing where
    messages can be prioritized based on geographic proximity.
    """
    latitude: float = Field(..., ge=-90, le=90, description="Latitude in degrees")
    longitude: float = Field(..., ge=-180, le=180, description="Longitude in degrees")
    accuracy_meters: Optional[float] = Field(None, ge=0, description="GPS accuracy in meters")
    altitude_meters: Optional[float] = Field(None, description="Altitude in meters")


class NodeIdentity(BaseModel):
    """
    Cryptographic identity for a P2P node.
    
    In a production system, this would use libp2p's peer identity system
    based on public/private key pairs (typically Ed25519 or RSA).
    
    The public_key serves as the node's unique identifier and enables:
    - Message signing for authenticity verification
    - Encrypted point-to-point communication
    - Reputation systems for trust management
    
    For offline/mesh scenarios:
    - Keys are generated locally on device
    - No certificate authority needed
    - Identity persists across network partitions
    """
    node_id: str = Field(..., description="Unique node identifier (derived from public key)")
    public_key: str = Field(..., description="Base64-encoded public key")
    display_name: Optional[str] = Field(None, description="Human-readable node name")
    
    @classmethod
    def generate_conceptual(cls, display_name: Optional[str] = None) -> "NodeIdentity":
        """
        Generate a conceptual node identity.
        
        In production, this would use cryptographic key generation:
        - private_key, public_key = generate_keypair()
        - node_id = hash(public_key)
        """
        import hashlib
        import secrets
        
        # Simulate key generation (conceptual)
        mock_public_key = secrets.token_hex(32)
        node_id = hashlib.sha256(mock_public_key.encode()).hexdigest()[:16]
        
        return cls(
            node_id=node_id,
            public_key=mock_public_key,
            display_name=display_name or f"Node-{node_id[:6]}"
        )


class HelpRequest(BaseModel):
    """
    Core message type for help requests in the disaster response network.
    
    Message Lifecycle:
    1. Created by a node when help is needed
    2. Signed with the sender's private key (conceptual)
    3. Published to the gossip network
    4. Propagated via gossip protocol to all peers
    5. Stored locally by each receiving node
    6. Expires after TTL seconds
    
    Gossip Protocol Properties:
    - Epidemic dissemination ensures high reliability
    - UUID prevents duplicate processing
    - TTL prevents infinite propagation
    - Hop count can limit network diameter
    
    Offline/Mesh Considerations:
    - Messages queue when no peers available
    - Sync occurs when nodes come into range
    - TTL-based expiry prevents stale data accumulation
    - Geolocation enables proximity-based prioritization
    """
    # Unique identifier for deduplication
    id: str = Field(default_factory=lambda: str(uuid4()), description="Unique message UUID")
    
    # Temporal fields
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Creation timestamp (UTC)")
    ttl_seconds: int = Field(default=3600, ge=60, le=86400, description="Time-to-live in seconds")
    
    # Geographic context
    location: GeoLocation = Field(..., description="Location where help is needed")
    
    # Request details
    request_type: RequestType = Field(..., description="Category of help needed")
    priority: RequestPriority = Field(default=RequestPriority.MEDIUM, description="Urgency level")
    title: str = Field(..., min_length=5, max_length=100, description="Brief description")
    description: str = Field(..., min_length=10, max_length=1000, description="Detailed description")
    contact_info: Optional[str] = Field(None, description="How to reach the requester")
    
    # Network metadata
    sender_id: str = Field(..., description="Node ID of the sender")
    hop_count: int = Field(default=0, ge=0, description="Number of hops from origin")
    signature: Optional[str] = Field(None, description="Cryptographic signature (conceptual)")
    
    def is_expired(self) -> bool:
        """Check if the message has exceeded its TTL."""
        age = (datetime.utcnow() - self.timestamp).total_seconds()
        return age > self.ttl_seconds
    
    def increment_hop(self) -> "HelpRequest":
        """Create a copy with incremented hop count for forwarding."""
        return self.model_copy(update={"hop_count": self.hop_count + 1})
    
    def to_gossip_message(self) -> dict:
        """Serialize for gossip protocol transmission."""
        return self.model_dump(mode="json")
    
    @classmethod
    def from_gossip_message(cls, data: dict) -> "HelpRequest":
        """Deserialize from gossip protocol message."""
        return cls.model_validate(data)


class HelpRequestCreate(BaseModel):
    """
    API input model for creating new help requests.
    
    This is the simplified input from API clients.
    The full HelpRequest is constructed by adding network metadata.
    """
    location: GeoLocation
    request_type: RequestType
    priority: RequestPriority = RequestPriority.MEDIUM
    title: str = Field(..., min_length=5, max_length=100)
    description: str = Field(..., min_length=10, max_length=1000)
    contact_info: Optional[str] = None
    ttl_seconds: int = Field(default=3600, ge=60, le=86400)


class PeerInfo(BaseModel):
    """
    Information about a known peer in the network.
    
    In production libp2p:
    - multiaddr contains transport-specific addressing
    - Example: /ip4/192.168.1.1/tcp/4001/p2p/QmNodeId
    
    For Bluetooth/Wi-Fi Direct:
    - multiaddr could be: /bluetooth/AA:BB:CC:DD:EE:FF
    - Or: /wifi-direct/DIRECT-xx-DeviceName
    """
    node_id: str = Field(..., description="Peer's node identifier")
    multiaddr: str = Field(..., description="libp2p multiaddress for connecting")
    last_seen: datetime = Field(default_factory=datetime.utcnow)
    is_active: bool = Field(default=True)
    latency_ms: Optional[float] = Field(None, description="Last measured latency")


class NetworkStats(BaseModel):
    """Statistics about the local node's network state."""
    node_id: str
    connected_peers: int
    known_peers: int
    messages_received: int
    messages_sent: int
    messages_stored: int
    uptime_seconds: float
