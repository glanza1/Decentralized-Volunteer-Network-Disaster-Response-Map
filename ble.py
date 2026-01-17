"""
ble.py - Bluetooth Low Energy Layer for Decentralized Disaster Response System

This module implements BLE communication for device-to-device messaging
when internet/WiFi is unavailable. Uses bleak for scanning and 
bluez-peripheral for GATT server functionality.

Architecture:
- Each device runs both as Peripheral (GATT Server) AND Central (Scanner)
- Custom GATT service for disaster messaging
- Gossip-style message propagation over BLE

Requirements:
- Linux with BlueZ 5.43+ 
- Bluetooth adapter with BLE support
- Run with appropriate permissions (or add user to bluetooth group)

Usage:
    ble_node = BLENode(node_id="abc123", on_message=callback)
    await ble_node.start()
"""

import asyncio
import logging
import json
import struct
from typing import Optional, Callable, Dict, Set, List, Any
from datetime import datetime
from dataclasses import dataclass, field
from uuid import uuid4

# BLE Libraries
from bleak import BleakScanner, BleakClient
from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData

# bluez-peripheral for GATT server (Linux only)
try:
    from bluez_peripheral.gatt.service import Service
    from bluez_peripheral.gatt.characteristic import characteristic, CharacteristicFlags
    from bluez_peripheral.advert import Advertisement
    from bluez_peripheral.agent import NoIoAgent
    from bluez_peripheral.util import get_message_bus, Adapter
    PERIPHERAL_AVAILABLE = True
except ImportError:
    PERIPHERAL_AVAILABLE = False

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════════════
# GATT SERVICE DEFINITIONS
# ═══════════════════════════════════════════════════════════════════════════

# Custom UUIDs for Disaster Response Service
DISASTER_SERVICE_UUID = "0000fff0-0000-1000-8000-00805f9b34fb"
MESSAGE_TX_UUID = "0000fff1-0000-1000-8000-00805f9b34fb"  # Write - send messages
MESSAGE_RX_UUID = "0000fff2-0000-1000-8000-00805f9b34fb"  # Read/Notify - receive messages
NODE_INFO_UUID = "0000fff3-0000-1000-8000-00805f9b34fb"   # Read - node identity

# BLE Configuration
BLE_SCAN_INTERVAL = 10.0  # Seconds between scans
BLE_CONNECTION_TIMEOUT = 10.0
MAX_MESSAGE_SIZE = 512  # BLE characteristic max size
MESSAGE_QUEUE_SIZE = 100


@dataclass
class BLEPeer:
    """Information about a discovered BLE peer."""
    address: str
    name: Optional[str]
    node_id: Optional[str] = None
    rssi: int = -100
    last_seen: datetime = field(default_factory=datetime.utcnow)
    is_connected: bool = False
    
    @property
    def is_disaster_node(self) -> bool:
        """Check if this peer appears to be a disaster response node."""
        return self.name and "Disaster" in self.name


@dataclass
class BLEMessage:
    """Message format for BLE transmission."""
    topic: str
    payload: dict
    sender_id: str
    message_id: str
    timestamp: float = field(default_factory=lambda: datetime.utcnow().timestamp())
    
    def to_bytes(self) -> bytes:
        """Serialize message to bytes for BLE transmission."""
        data = json.dumps({
            "t": self.topic,
            "p": self.payload,
            "s": self.sender_id,
            "m": self.message_id,
            "ts": self.timestamp
        }, separators=(',', ':')).encode('utf-8')
        return data
    
    @classmethod
    def from_bytes(cls, data: bytes) -> 'BLEMessage':
        """Deserialize message from bytes."""
        d = json.loads(data.decode('utf-8'))
        return cls(
            topic=d.get("t", ""),
            payload=d.get("p", {}),
            sender_id=d.get("s", ""),
            message_id=d.get("m", ""),
            timestamp=d.get("ts", datetime.utcnow().timestamp())
        )


# ═══════════════════════════════════════════════════════════════════════════
# GATT SERVER (Peripheral Mode)
# ═══════════════════════════════════════════════════════════════════════════

if PERIPHERAL_AVAILABLE:
    class DisasterService(Service):
        """
        Custom GATT Service for Disaster Response messaging.
        
        Characteristics:
        - MESSAGE_TX: Write - other devices write messages here
        - MESSAGE_RX: Read/Notify - devices read messages from here
        - NODE_INFO: Read - this node's identity information
        """
        
        def __init__(self, node_id: str, node_name: str, on_message: Optional[Callable] = None):
            super().__init__(DISASTER_SERVICE_UUID, True)
            self.node_id = node_id
            self.node_name = node_name
            self.on_message = on_message
            self._pending_messages: List[bytes] = []
            self._message_index = 0
            
        @characteristic(MESSAGE_TX_UUID, CharacteristicFlags.WRITE)
        def message_tx(self, options):
            """Characteristic for receiving messages from other devices."""
            # This is write-only, read returns empty
            return bytes()
        
        @message_tx.setter
        def message_tx(self, value: bytes, options):
            """Handle incoming message from another device."""
            try:
                message = BLEMessage.from_bytes(value)
                logger.info(f"BLE received message from {message.sender_id}: {message.message_id}")
                
                if self.on_message:
                    # Call the message handler
                    self.on_message(message)
                    
            except Exception as e:
                logger.error(f"Failed to parse BLE message: {e}")
        
        @characteristic(MESSAGE_RX_UUID, CharacteristicFlags.READ | CharacteristicFlags.NOTIFY)
        def message_rx(self, options) -> bytes:
            """Characteristic for broadcasting messages to connected devices."""
            if self._pending_messages:
                return self._pending_messages[-1]
            return bytes()
        
        def broadcast_message(self, message: BLEMessage):
            """Add a message to be broadcast via notifications."""
            data = message.to_bytes()
            if len(data) <= MAX_MESSAGE_SIZE:
                self._pending_messages.append(data)
                # Keep only recent messages
                if len(self._pending_messages) > MESSAGE_QUEUE_SIZE:
                    self._pending_messages.pop(0)
                # Trigger notification (if supported)
                # Note: bluez-peripheral handles notifications internally
        
        @characteristic(NODE_INFO_UUID, CharacteristicFlags.READ)
        def node_info(self, options) -> bytes:
            """Return this node's identity information."""
            info = json.dumps({
                "node_id": self.node_id,
                "name": self.node_name,
                "version": "1.0"
            }).encode('utf-8')
            return info


# ═══════════════════════════════════════════════════════════════════════════
# BLE NODE (Combined Central + Peripheral)
# ═══════════════════════════════════════════════════════════════════════════

class BLENode:
    """
    BLE Node that operates as both Central (scanner) and Peripheral (GATT server).
    
    Features:
    - Scans for nearby disaster response devices
    - Runs GATT server for receiving messages
    - Sends messages to discovered peers
    - Deduplicates messages using message IDs
    """
    
    def __init__(
        self,
        node_id: str,
        node_name: str = "DisasterNode",
        on_message: Optional[Callable[[BLEMessage], None]] = None
    ):
        self.node_id = node_id
        self.node_name = f"Disaster-{node_name[:8]}"
        self.on_message = on_message
        
        # Peer tracking
        self._peers: Dict[str, BLEPeer] = {}
        self._connected_clients: Dict[str, BleakClient] = {}
        
        # Message deduplication
        self._seen_messages: Set[str] = set()
        
        # State
        self._running = False
        self._tasks: List[asyncio.Task] = []
        
        # GATT Server components (Linux only)
        self._service: Optional[Any] = None
        self._bus = None
        self._adapter = None
        self._advert = None
        
        # Statistics
        self._messages_sent = 0
        self._messages_received = 0
        self._start_time = datetime.utcnow()
        
        logger.info(f"BLE Node created: {self.node_id} ({self.node_name})")
    
    async def start(self) -> None:
        """Start the BLE node (scanner + GATT server)."""
        self._running = True
        self._start_time = datetime.utcnow()
        
        # Start GATT server (Linux only)
        if PERIPHERAL_AVAILABLE:
            await self._start_gatt_server()
        else:
            logger.warning("bluez-peripheral not available, running in Central-only mode")
        
        # Start background tasks
        self._tasks = [
            asyncio.create_task(self._scan_loop()),
            asyncio.create_task(self._connection_maintenance_loop()),
        ]
        
        logger.info(f"BLE Node started: {self.node_name}")
    
    async def stop(self) -> None:
        """Stop the BLE node."""
        self._running = False
        
        # Close client connections
        for address, client in list(self._connected_clients.items()):
            try:
                await client.disconnect()
            except:
                pass
        self._connected_clients.clear()
        
        # Stop tasks
        for task in self._tasks:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        self._tasks.clear()
        
        # Stop advertisement
        if self._advert:
            try:
                await self._advert.unregister()
            except:
                pass
        
        logger.info("BLE Node stopped")
    
    async def _start_gatt_server(self) -> None:
        """Start the GATT server for receiving messages."""
        try:
            # Get D-Bus connection
            self._bus = await get_message_bus()
            
            # Get Bluetooth adapter
            self._adapter = await Adapter.get_first(self._bus)
            
            # Create and register the disaster service
            self._service = DisasterService(
                node_id=self.node_id,
                node_name=self.node_name,
                on_message=self._handle_incoming_message
            )
            await self._service.register(self._bus)
            
            # Create and register advertisement
            self._advert = Advertisement(
                localName=self.node_name,
                serviceUUIDs=[DISASTER_SERVICE_UUID],
                appearance=0x0000,
                timeout=0  # Don't timeout
            )
            await self._advert.register(self._bus, self._adapter)
            
            logger.info(f"GATT server started, advertising as: {self.node_name}")
            
        except Exception as e:
            logger.error(f"Failed to start GATT server: {e}")
            logger.warning("Continuing in Central-only mode")
    
    async def _scan_loop(self) -> None:
        """Continuously scan for nearby disaster response devices."""
        while self._running:
            try:
                logger.debug("Starting BLE scan...")
                
                # Scan for devices
                devices = await BleakScanner.discover(
                    timeout=5.0,
                    return_adv=True
                )
                
                for device, adv_data in devices.values():
                    await self._process_discovered_device(device, adv_data)
                
                # Log discovery stats
                disaster_nodes = [p for p in self._peers.values() if p.is_disaster_node]
                if disaster_nodes:
                    logger.info(f"Found {len(disaster_nodes)} disaster response nodes nearby")
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"BLE scan error: {e}")
            
            await asyncio.sleep(BLE_SCAN_INTERVAL)
    
    async def _process_discovered_device(
        self, 
        device: BLEDevice, 
        adv_data: AdvertisementData
    ) -> None:
        """Process a discovered BLE device."""
        # Check if it's a disaster response node (by name or service UUID)
        is_disaster_node = False
        
        if adv_data.local_name and "Disaster" in adv_data.local_name:
            is_disaster_node = True
        
        if adv_data.service_uuids:
            if DISASTER_SERVICE_UUID in [str(u).lower() for u in adv_data.service_uuids]:
                is_disaster_node = True
        
        if not is_disaster_node:
            return
        
        # Update or create peer entry
        if device.address in self._peers:
            peer = self._peers[device.address]
            peer.last_seen = datetime.utcnow()
            peer.rssi = adv_data.rssi or -100
        else:
            peer = BLEPeer(
                address=device.address,
                name=adv_data.local_name,
                rssi=adv_data.rssi or -100
            )
            self._peers[device.address] = peer
            logger.info(f"Discovered new disaster node: {peer.name} ({peer.address})")
    
    async def _connection_maintenance_loop(self) -> None:
        """Maintain connections to discovered disaster nodes."""
        while self._running:
            try:
                # Try to connect to unconnected peers
                for address, peer in list(self._peers.items()):
                    if not peer.is_disaster_node:
                        continue
                    
                    if address not in self._connected_clients:
                        await self._connect_to_peer(peer)
                
                # Clean up stale peers (not seen in 5 minutes)
                cutoff = datetime.utcnow().timestamp() - 300
                stale = [
                    addr for addr, peer in self._peers.items()
                    if peer.last_seen.timestamp() < cutoff
                ]
                for addr in stale:
                    self._peers.pop(addr, None)
                    self._connected_clients.pop(addr, None)
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Connection maintenance error: {e}")
            
            await asyncio.sleep(30)  # Check every 30 seconds
    
    async def _connect_to_peer(self, peer: BLEPeer) -> bool:
        """Connect to a peer and read its node info."""
        try:
            logger.info(f"Connecting to peer: {peer.address}")
            
            client = BleakClient(peer.address, timeout=BLE_CONNECTION_TIMEOUT)
            await client.connect()
            
            if client.is_connected:
                peer.is_connected = True
                self._connected_clients[peer.address] = client
                
                # Read node info
                try:
                    node_info_data = await client.read_gatt_char(NODE_INFO_UUID)
                    node_info = json.loads(node_info_data.decode('utf-8'))
                    peer.node_id = node_info.get("node_id")
                    logger.info(f"Connected to peer: {peer.node_id}")
                except Exception as e:
                    logger.warning(f"Could not read node info: {e}")
                
                # Subscribe to message notifications
                try:
                    await client.start_notify(MESSAGE_RX_UUID, self._on_notification)
                except Exception as e:
                    logger.warning(f"Could not subscribe to notifications: {e}")
                
                return True
            
        except Exception as e:
            logger.debug(f"Failed to connect to {peer.address}: {e}")
            peer.is_connected = False
        
        return False
    
    def _on_notification(self, characteristic, data: bytes) -> None:
        """Handle notification from a connected peer."""
        try:
            message = BLEMessage.from_bytes(data)
            self._handle_incoming_message(message)
        except Exception as e:
            logger.error(f"Failed to parse notification: {e}")
    
    def _handle_incoming_message(self, message: BLEMessage) -> None:
        """Handle an incoming BLE message."""
        # Deduplicate
        if message.message_id in self._seen_messages:
            return
        self._seen_messages.add(message.message_id)
        
        # Limit cache size
        if len(self._seen_messages) > 5000:
            self._seen_messages = set(list(self._seen_messages)[-2500:])
        
        self._messages_received += 1
        
        # Call external handler
        if self.on_message:
            self.on_message(message)
        
        logger.info(f"BLE message received: {message.topic} from {message.sender_id}")
    
    async def broadcast(self, topic: str, payload: dict) -> int:
        """
        Broadcast a message to all connected peers.
        
        Returns:
            Number of peers the message was sent to.
        """
        message = BLEMessage(
            topic=topic,
            payload=payload,
            sender_id=self.node_id,
            message_id=str(uuid4())
        )
        
        # Mark as seen to prevent echo
        self._seen_messages.add(message.message_id)
        
        # Broadcast via GATT server (for connected centrals)
        if self._service:
            self._service.broadcast_message(message)
        
        # Send to connected peers (as central)
        sent_count = 0
        data = message.to_bytes()
        
        for address, client in list(self._connected_clients.items()):
            try:
                if client.is_connected:
                    await client.write_gatt_char(MESSAGE_TX_UUID, data)
                    sent_count += 1
                else:
                    # Clean up disconnected client
                    self._connected_clients.pop(address, None)
                    if address in self._peers:
                        self._peers[address].is_connected = False
            except Exception as e:
                logger.warning(f"Failed to send to {address}: {e}")
                self._connected_clients.pop(address, None)
        
        self._messages_sent += 1
        logger.info(f"BLE broadcast to {sent_count} peers: {message.message_id}")
        
        return sent_count
    
    def get_stats(self) -> dict:
        """Get BLE node statistics."""
        uptime = (datetime.utcnow() - self._start_time).total_seconds()
        connected_count = sum(1 for p in self._peers.values() if p.is_connected)
        
        return {
            "node_id": self.node_id,
            "node_name": self.node_name,
            "uptime_seconds": uptime,
            "discovered_peers": len(self._peers),
            "connected_peers": connected_count,
            "messages_sent": self._messages_sent,
            "messages_received": self._messages_received,
            "peripheral_available": PERIPHERAL_AVAILABLE
        }
    
    def get_peers(self) -> List[dict]:
        """Get list of discovered peers."""
        return [
            {
                "address": peer.address,
                "name": peer.name,
                "node_id": peer.node_id,
                "rssi": peer.rssi,
                "is_connected": peer.is_connected,
                "last_seen": peer.last_seen.isoformat()
            }
            for peer in self._peers.values()
            if peer.is_disaster_node
        ]


# ═══════════════════════════════════════════════════════════════════════════
# GLOBAL INSTANCE MANAGEMENT
# ═══════════════════════════════════════════════════════════════════════════

_ble_node: Optional[BLENode] = None


def get_ble_node() -> Optional[BLENode]:
    """Get the global BLE node instance."""
    return _ble_node


async def init_ble_node(
    node_id: str,
    node_name: str = "DisasterNode",
    on_message: Optional[Callable[[BLEMessage], None]] = None
) -> BLENode:
    """Initialize and start the global BLE node."""
    global _ble_node
    
    _ble_node = BLENode(
        node_id=node_id,
        node_name=node_name,
        on_message=on_message
    )
    await _ble_node.start()
    
    return _ble_node


async def stop_ble_node() -> None:
    """Stop the global BLE node."""
    global _ble_node
    
    if _ble_node:
        await _ble_node.stop()
        _ble_node = None
