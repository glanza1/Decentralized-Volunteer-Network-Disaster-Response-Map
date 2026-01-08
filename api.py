"""
api.py - FastAPI Router for Decentralized Disaster Response System

This module defines the REST API endpoints for the disaster response system.
The API layer is cleanly separated from the P2P networking layer.

API Design:
- RESTful endpoints for creating and querying help requests
- Async handlers for non-blocking P2P operations
- Pydantic models for input validation
- Comprehensive error handling
- API key authentication for protected endpoints

Note: In a fully decentralized system, this API is for LOCAL access only.
Each node exposes its own API, there is no central server.
"""

from fastapi import APIRouter, HTTPException, Query, Depends
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
from security import get_api_key, get_optional_api_key, SECURITY_ENABLED

# Blockchain integration (optional - gracefully handle if not available)
try:
    from blockchain import get_blockchain
    BLOCKCHAIN_ENABLED = True
except ImportError:
    BLOCKCHAIN_ENABLED = False

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
    4. 🔗 Optionally recorded on blockchain for trust verification
    
    In offline/mesh scenarios, the message would queue locally and
    sync to peers when they come into range.
    """
)
async def create_help_request(
    request: HelpRequestCreate,
    api_key: str = Depends(get_api_key)  # 🔐 Requires valid API key
) -> HelpRequest:
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
        
        # 🔗 Create task on blockchain (if available)
        blockchain_tx = None
        if BLOCKCHAIN_ENABLED:
            try:
                bc = get_blockchain()
                blockchain_tx = bc.create_task(
                    task_id=help_request.id,
                    latitude=help_request.location.latitude,
                    longitude=help_request.location.longitude,
                    request_type=help_request.request_type.value,
                    priority=help_request.priority.value,
                    content_hash=f"ipfs://{help_request.id}",  # Placeholder
                    ttl_seconds=help_request.ttl_seconds
                )
                logger.info(f"🔗 Blockchain task created: {blockchain_tx}")
            except Exception as e:
                logger.warning(f"Blockchain task creation failed (non-fatal): {e}")
        
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


# ═══════════════════════════════════════════════════════════════════════════
# 🔗 BLOCKCHAIN-INTEGRATED HELP REQUEST ACTIONS
# ═══════════════════════════════════════════════════════════════════════════

@router.post(
    "/help-request/{request_id}/verify",
    summary="🔗 Verify a help request (blockchain)",
    description="""
    Verify that a help request is legitimate.
    
    - Requires trust level 2+ on blockchain
    - Adds verification score to the request
    - Rewards verifier with +5 reputation points
    """
)
async def verify_help_request(
    request_id: str,
    api_key: str = Depends(get_api_key)
) -> dict:
    """Verify a help request on blockchain."""
    # Check request exists
    message = message_storage.get(request_id)
    if not message:
        raise HTTPException(status_code=404, detail="Help request not found")
    
    if not BLOCKCHAIN_ENABLED:
        raise HTTPException(status_code=503, detail="Blockchain not available")
    
    try:
        bc = get_blockchain()
        tx_hash = bc.verify_task(request_id)
        
        if tx_hash:
            logger.info(f"🔗 Help request verified on blockchain: {request_id}")
            return {
                "success": True,
                "request_id": request_id,
                "transaction": tx_hash,
                "message": "Request verified! You earned +5 reputation points.",
                "reward_points": 5
            }
        else:
            raise HTTPException(status_code=400, detail="Verification failed")
            
    except Exception as e:
        logger.error(f"Blockchain verify error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/help-request/{request_id}/accept",
    summary="🔗 Accept/volunteer for a help request (blockchain)",
    description="""
    Accept a help request as a volunteer.
    
    - Assigns you to the task on blockchain
    - Updates task status to IN_PROGRESS
    """
)
async def accept_help_request(
    request_id: str,
    api_key: str = Depends(get_api_key)
) -> dict:
    """Accept a help request on blockchain."""
    message = message_storage.get(request_id)
    if not message:
        raise HTTPException(status_code=404, detail="Help request not found")
    
    if not BLOCKCHAIN_ENABLED:
        raise HTTPException(status_code=503, detail="Blockchain not available")
    
    try:
        bc = get_blockchain()
        tx_hash = bc.accept_task(request_id)
        
        if tx_hash:
            logger.info(f"🔗 Help request accepted on blockchain: {request_id}")
            return {
                "success": True,
                "request_id": request_id,
                "transaction": tx_hash,
                "message": "You accepted this request! Complete it to earn +50 reputation points.",
                "status": "IN_PROGRESS"
            }
        else:
            raise HTTPException(status_code=400, detail="Accept failed")
            
    except Exception as e:
        logger.error(f"Blockchain accept error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/help-request/{request_id}/complete",
    summary="🔗 Mark help request as completed (blockchain)",
    description="""
    Mark a help request as completed (by the request creator).
    
    - Only the original requester can mark as complete
    - Rewards the volunteer with +50 reputation points (+100 for critical)
    - Rewards the requester with +10 reputation points
    """
)
async def complete_help_request(
    request_id: str,
    api_key: str = Depends(get_api_key)
) -> dict:
    """Complete a help request on blockchain."""
    message = message_storage.get(request_id)
    if not message:
        raise HTTPException(status_code=404, detail="Help request not found")
    
    if not BLOCKCHAIN_ENABLED:
        raise HTTPException(status_code=503, detail="Blockchain not available")
    
    try:
        bc = get_blockchain()
        tx_hash = bc.complete_task(request_id)
        
        if tx_hash:
            # Calculate reward based on priority
            reward = 50
            if message.priority.value == "critical":
                reward = 100
            
            logger.info(f"🔗 Help request completed on blockchain: {request_id}")
            return {
                "success": True,
                "request_id": request_id,
                "transaction": tx_hash,
                "message": f"Task completed! Volunteer earned +{reward} reputation points.",
                "volunteer_reward": reward,
                "creator_reward": 10,
                "status": "COMPLETED"
            }
        else:
            raise HTTPException(status_code=400, detail="Complete failed")
            
    except Exception as e:
        logger.error(f"Blockchain complete error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/help-request/{request_id}/blockchain-status",
    summary="🔗 Get blockchain status for a help request",
    description="Get the blockchain verification status and trust info for a help request."
)
async def get_blockchain_status(request_id: str) -> dict:
    """Get blockchain status for a help request."""
    message = message_storage.get(request_id)
    if not message:
        raise HTTPException(status_code=404, detail="Help request not found")
    
    if not BLOCKCHAIN_ENABLED:
        return {
            "blockchain_enabled": False,
            "request_id": request_id,
            "message": "Blockchain not available"
        }
    
    try:
        bc = get_blockchain()
        status = bc.get_task_status(request_id)
        
        return {
            "blockchain_enabled": True,
            "request_id": request_id,
            "status": status.get("status", "UNKNOWN") if status else "NOT_ON_CHAIN",
            "verification_score": status.get("verificationScore", 0) if status else 0,
            "assigned_volunteer": status.get("assignedVolunteer") if status else None,
            "is_verified": status.get("verificationScore", 0) >= 10 if status else False
        }
        
    except Exception as e:
        logger.error(f"Blockchain status error: {e}")
        return {
            "blockchain_enabled": True,
            "request_id": request_id,
            "status": "ERROR",
            "error": str(e)
        }
