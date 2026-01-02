"""
api.py - FastAPI Router for Decentralized Disaster Response System

This module defines the REST API endpoints for the disaster response system.
The API layer is cleanly separated from the P2P networking layer.

API Design:
- RESTful endpoints for creating and querying help requests
- Async handlers for non-blocking P2P operations
- Pydantic models for input validation
- Comprehensive error handling

Note: In a fully decentralized system, this API is for LOCAL access only.
Each node exposes its own API, there is no central server.
"""

from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
from datetime import datetime
import logging

from models import (
    HelpRequest,
    HelpRequestCreate,
    GeoLocation,
    NetworkStats,
    PeerInfo,
    RequestType,
    RequestPriority
)
from storage import message_storage
from p2p import get_p2p_node, GossipTopic

logger = logging.getLogger(__name__)

# Create API router
router = APIRouter(tags=["Disaster Response"])


@router.post(
    "/help-request",
    response_model=HelpRequest,
    status_code=201,
    summary="Create and broadcast a help request",
    description="""
    Creates a new help request and broadcasts it to the P2P network.
    
    The request is:
    1. Validated and enriched with metadata (UUID, timestamp, sender ID)
    2. Stored locally in the node's message storage
    3. Published to the gossip network for propagation to all peers
    
    In offline/mesh scenarios, the message would queue locally and
    sync to peers when they come into range.
    """
)
async def create_help_request(request: HelpRequestCreate) -> HelpRequest:
    """
    Create and broadcast a new help request.
    
    This endpoint is the primary way for users to request help during disasters.
    The message is immediately stored locally and broadcast to all connected peers.
    """
    try:
        p2p_node = get_p2p_node()
        
        # Create full HelpRequest from input
        help_request = HelpRequest(
            location=request.location,
            request_type=request.request_type,
            priority=request.priority,
            title=request.title,
            description=request.description,
            contact_info=request.contact_info,
            ttl_seconds=request.ttl_seconds,
            sender_id=p2p_node.identity.node_id
        )
        
        # Store locally first
        stored = message_storage.store(help_request)
        if not stored:
            logger.warning(f"Failed to store message locally: {help_request.id}")
        
        # Broadcast to P2P network
        await p2p_node.publish(
            GossipTopic.HELP_REQUESTS,
            help_request.to_gossip_message()
        )
        
        logger.info(f"Created and broadcast help request: {help_request.id}")
        return help_request
        
    except Exception as e:
        logger.error(f"Error creating help request: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/local-requests",
    response_model=List[HelpRequest],
    summary="Get locally stored help requests",
    description="""
    Returns all help requests stored locally on this node.
    
    This includes:
    - Requests created by this node
    - Requests received from peers via gossip
    
    Expired messages (past TTL) are excluded by default.
    Results are sorted by timestamp (newest first).
    """
)
async def get_local_requests(
    request_type: Optional[RequestType] = Query(
        None,
        description="Filter by request type"
    ),
    priority: Optional[RequestPriority] = Query(
        None,
        description="Filter by priority level"
    ),
    include_expired: bool = Query(
        False,
        description="Include expired messages"
    ),
    limit: int = Query(
        100,
        ge=1,
        le=1000,
        description="Maximum number of results"
    )
) -> List[HelpRequest]:
    """
    Retrieve locally stored help requests with optional filtering.
    """
    try:
        # Get all messages
        messages = message_storage.get_all(include_expired=include_expired)
        
        # Apply filters
        if request_type:
            messages = [m for m in messages if m.request_type == request_type]
        
        if priority:
            messages = [m for m in messages if m.priority == priority]
        
        # Apply limit
        return messages[:limit]
        
    except Exception as e:
        logger.error(f"Error retrieving local requests: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/local-requests/{request_id}",
    response_model=HelpRequest,
    summary="Get a specific help request by ID",
    description="Retrieves a single help request by its UUID."
)
async def get_help_request(request_id: str) -> HelpRequest:
    """
    Retrieve a specific help request by ID.
    """
    message = message_storage.get(request_id)
    if not message:
        raise HTTPException(status_code=404, detail="Help request not found")
    return message


@router.get(
    "/nearby-requests",
    response_model=List[HelpRequest],
    summary="Get help requests near a location",
    description="""
    Returns help requests within a specified radius of a location.
    
    This is useful for:
    - Finding nearby incidents to respond to
    - Location-based filtering on mobile devices
    - Prioritizing local emergencies
    
    Uses Haversine formula for distance calculation.
    """
)
async def get_nearby_requests(
    latitude: float = Query(..., ge=-90, le=90, description="Latitude"),
    longitude: float = Query(..., ge=-180, le=180, description="Longitude"),
    radius_km: float = Query(
        10.0,
        ge=0.1,
        le=100,
        description="Search radius in kilometers"
    ),
    limit: int = Query(50, ge=1, le=200, description="Maximum results")
) -> List[HelpRequest]:
    """
    Get help requests near a specified location.
    """
    try:
        location = GeoLocation(latitude=latitude, longitude=longitude)
        nearby = message_storage.get_nearby(location, radius_km)
        return nearby[:limit]
        
    except Exception as e:
        logger.error(f"Error finding nearby requests: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/network/stats",
    response_model=NetworkStats,
    summary="Get network statistics",
    description="""
    Returns statistics about this node's network state.
    
    Includes:
    - Node identity information
    - Peer connection counts
    - Message statistics
    - Uptime
    """
)
async def get_network_stats() -> NetworkStats:
    """
    Get current network statistics for this node.
    """
    try:
        p2p_node = get_p2p_node()
        p2p_stats = p2p_node.get_stats()
        storage_stats = message_storage.get_stats()
        
        return NetworkStats(
            node_id=p2p_stats["node_id"],
            connected_peers=p2p_stats["connected_peers"],
            known_peers=p2p_stats["known_peers"],
            messages_received=p2p_stats["messages_received"],
            messages_sent=p2p_stats["messages_sent"],
            messages_stored=storage_stats["total_stored"],
            uptime_seconds=p2p_stats["uptime_seconds"]
        )
        
    except Exception as e:
        logger.error(f"Error getting network stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/network/peers",
    response_model=List[PeerInfo],
    summary="Get connected peers",
    description="Returns information about known peers in the network."
)
async def get_peers() -> List[PeerInfo]:
    """
    Get list of known peers.
    """
    try:
        p2p_node = get_p2p_node()
        return p2p_node.get_peers()
        
    except Exception as e:
        logger.error(f"Error getting peers: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/storage/stats",
    summary="Get storage statistics",
    description="Returns detailed statistics about local message storage."
)
async def get_storage_stats() -> dict:
    """
    Get storage statistics.
    """
    return message_storage.get_stats()


@router.post(
    "/storage/cleanup",
    summary="Trigger storage cleanup",
    description="Manually trigger cleanup of expired messages."
)
async def trigger_cleanup() -> dict:
    """
    Trigger manual cleanup of expired messages.
    """
    cleaned = message_storage.cleanup_expired()
    return {"cleaned_messages": cleaned}
