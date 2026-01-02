"""
main.py - Entry Point for Decentralized Disaster Response System

A P2P backend prototype demonstrating a decentralized architecture for
disaster response coordination. Each node acts as both client and server,
enabling resilient communication without central infrastructure.

Architecture Overview:
======================
┌─────────────────────────────────────────────────────────────────┐
│                         NODE ARCHITECTURE                        │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────┐     ┌──────────────┐     ┌─────────────────┐  │
│  │   FastAPI   │────▶│   Storage    │◀────│    P2P Layer    │  │
│  │   (api.py)  │     │ (storage.py) │     │    (p2p.py)     │  │
│  └─────────────┘     └──────────────┘     └─────────────────┘  │
│        │                    │                      │            │
│        │              ┌─────▼─────┐                │            │
│        └─────────────▶│  Models   │◀───────────────┘            │
│                       │(models.py)│                             │
│                       └───────────┘                             │
└─────────────────────────────────────────────────────────────────┘

P2P Network Topology (Gossip-based):
====================================
     ┌──────┐         ┌──────┐
     │Node A│◀───────▶│Node B│
     └──┬───┘         └───┬──┘
        │                 │
        │   ┌──────┐     │
        └──▶│Node C│◀────┘
            └──┬───┘
               │
        ┌──────▼──────┐
        │   Node D    │  ◀── Your local node
        │ (this node) │
        └─────────────┘

Each node:
- Exposes a local REST API for user interaction
- Connects to peers via P2P protocols
- Subscribes to gossip topics for message propagation
- Stores messages locally for offline access

Usage:
======
1. Start a single node:
   python main.py

2. Start with specific port and bootstrap peer:
   python main.py --port 8001 --p2p-port 4002 --bootstrap /ip4/192.168.1.1/tcp/4001/p2p/NodeId

3. Access the API documentation:
   http://localhost:8000/docs

4. Create a help request:
   POST http://localhost:8000/api/help-request
   {
       "location": {"latitude": 41.0082, "longitude": 28.9784},
       "request_type": "medical",
       "priority": "high",
       "title": "Medical emergency at central plaza",
       "description": "Person injured, needs immediate medical attention."
   }

5. Get local requests:
   GET http://localhost:8000/api/local-requests

Offline/Mesh Networking (Conceptual):
=====================================
This prototype is designed with offline-first principles:

1. LOCAL OPERATION:
   - All data is stored locally on each node
   - The API works even when disconnected from peers
   - Messages queue for later synchronization

2. BLUETOOTH MESH (Conceptual):
   - Nodes would discover each other via BLE advertising
   - Small messages (< 512 bytes) sent via GATT
   - Larger payloads use BLE data transfer profiles

3. WI-FI DIRECT (Conceptual):
   - Automatic group formation without infrastructure
   - Higher bandwidth for bulk sync operations
   - Seamless handoff when nodes move

4. HYBRID APPROACH:
   - Use BLE for discovery and presence
   - Upgrade to Wi-Fi Direct for data sync
   - Fall back to queued messages when isolated

5. RESILIENCE:
   - No single point of failure
   - Partition-tolerant by design
   - Eventually consistent message delivery
"""

import asyncio
import argparse
import logging
import sys
from contextlib import asynccontextmanager
from typing import Optional, List

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from models import HelpRequest, NodeIdentity
from storage import message_storage
from p2p import init_p2p_node, get_p2p_node, GossipTopic
from api import router as api_router

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)


def create_message_handler():
    """
    Create a handler for incoming gossip messages.
    
    This handler is called whenever a HelpRequest message
    is received from the P2P network.
    """
    def handle_help_request(payload: dict) -> None:
        """Process incoming help request from the network."""
        try:
            # Reconstruct HelpRequest from payload
            help_request = HelpRequest.from_gossip_message(payload)
            
            # Increment hop count (message traveled through network)
            help_request = help_request.increment_hop()
            
            # Store in local storage
            stored = message_storage.store(help_request)
            
            if stored:
                logger.info(
                    f"Received help request from network: {help_request.id} "
                    f"(type: {help_request.request_type}, hops: {help_request.hop_count})"
                )
            else:
                logger.debug(f"Duplicate/expired message: {help_request.id}")
                
        except Exception as e:
            logger.error(f"Error processing incoming message: {e}")
    
    return handle_help_request


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manage application lifecycle.
    
    Startup:
    - Initialize P2P node
    - Subscribe to gossip topics
    - Start background tasks
    
    Shutdown:
    - Gracefully stop P2P node
    - Cleanup resources
    """
    logger.info("=" * 60)
    logger.info("DECENTRALIZED DISASTER RESPONSE SYSTEM")
    logger.info("=" * 60)
    
    # Get configuration from app state
    config = getattr(app.state, "config", {})
    
    # Initialize P2P node
    identity = NodeIdentity.generate_conceptual(
        display_name=config.get("node_name")
    )
    
    p2p_node = init_p2p_node(
        identity=identity,
        listen_port=config.get("p2p_port", 4001),
        bootstrap_peers=config.get("bootstrap_peers", [])
    )
    
    # Subscribe to help request topic
    p2p_node.subscribe(
        GossipTopic.HELP_REQUESTS,
        create_message_handler()
    )
    
    # Start P2P node
    await p2p_node.start()
    
    logger.info(f"Node ID: {identity.node_id}")
    logger.info(f"Display Name: {identity.display_name}")
    logger.info(f"P2P Port: {config.get('p2p_port', 4001)}")
    logger.info(f"API Port: {config.get('api_port', 8000)}")
    logger.info("=" * 60)
    
    yield
    
    # Shutdown
    logger.info("Shutting down...")
    await p2p_node.stop()
    logger.info("Shutdown complete")


def create_app(config: Optional[dict] = None) -> FastAPI:
    """
    Create and configure the FastAPI application.
    
    Args:
        config: Optional configuration dictionary.
        
    Returns:
        Configured FastAPI application.
    """
    app = FastAPI(
        title="Decentralized Disaster Response System",
        description="""
        A P2P backend prototype for coordinating disaster response without central servers.
        
        ## Features
        
        - **Decentralized**: No central server, each node is equal
        - **Gossip Protocol**: Messages propagate reliably across the network
        - **Offline-First**: Works locally, syncs when connected
        - **Geospatial**: Location-aware help request filtering
        
        ## Architecture
        
        Each node runs this API locally and connects to peers via P2P protocols.
        Help requests are broadcast through gossip-based pub/sub messaging.
        
        ## Conceptual Extensions
        
        This prototype could be extended for mesh networking via:
        - Bluetooth Low Energy for device discovery
        - Wi-Fi Direct for ad-hoc networking
        - LoRa for long-range communication
        """,
        version="0.1.0",
        lifespan=lifespan
    )
    
    # Store configuration for access during lifespan
    app.state.config = config or {}
    
    # Add CORS middleware (allow all for development)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Include API router
    app.include_router(api_router, prefix="/api")
    
    # Root endpoint
    @app.get("/", tags=["Health"])
    async def root():
        """Health check and node information."""
        try:
            p2p_node = get_p2p_node()
            stats = p2p_node.get_stats()
            return {
                "status": "online",
                "node_id": stats["node_id"],
                "display_name": stats["display_name"],
                "connected_peers": stats["connected_peers"],
                "messages_stored": message_storage.get_stats()["total_stored"],
                "api_docs": "/docs"
            }
        except Exception:
            return {
                "status": "starting",
                "message": "Node is initializing..."
            }
    
    @app.get("/health", tags=["Health"])
    async def health_check():
        """Simple health check endpoint."""
        return {"status": "healthy"}
    
    return app


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Decentralized Disaster Response System - P2P Node",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Start a single node
  python main.py
  
  # Start with custom ports
  python main.py --port 8001 --p2p-port 4002
  
  # Start with a bootstrap peer
  python main.py --bootstrap /ip4/192.168.1.1/tcp/4001/p2p/NodeId
  
  # Start with a custom node name
  python main.py --name "Relief Station Alpha"
        """
    )
    
    parser.add_argument(
        "--port", "-p",
        type=int,
        default=8000,
        help="HTTP API port (default: 8000)"
    )
    
    parser.add_argument(
        "--p2p-port",
        type=int,
        default=4001,
        help="P2P listen port (default: 4001)"
    )
    
    parser.add_argument(
        "--name", "-n",
        type=str,
        default=None,
        help="Node display name (auto-generated if not specified)"
    )
    
    parser.add_argument(
        "--bootstrap", "-b",
        type=str,
        action="append",
        default=[],
        help="Bootstrap peer multiaddress (can be specified multiple times)"
    )
    
    parser.add_argument(
        "--host",
        type=str,
        default="0.0.0.0",
        help="Host to bind to (default: 0.0.0.0)"
    )
    
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging"
    )
    
    return parser.parse_args()


def main():
    """Main entry point."""
    args = parse_args()
    
    # Configure logging level
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Create configuration
    config = {
        "api_port": args.port,
        "p2p_port": args.p2p_port,
        "node_name": args.name,
        "bootstrap_peers": args.bootstrap
    }
    
    # Create application
    app = create_app(config)
    
    # Run with uvicorn
    logger.info("Starting Decentralized Disaster Response System...")
    uvicorn.run(
        app,
        host=args.host,
        port=args.port,
        log_level="info" if not args.debug else "debug"
    )


if __name__ == "__main__":
    main()
