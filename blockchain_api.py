"""
blockchain_api.py - FastAPI Router for Blockchain Operations

This module provides REST API endpoints for interacting with the
disaster response smart contracts.
"""

from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, Field
from typing import Optional
import logging

logger = logging.getLogger(__name__)

# Create API router
router = APIRouter(prefix="/blockchain", tags=["Blockchain"])


# ===== Request/Response Models =====

class RegisterVolunteerRequest(BaseModel):
    """Request to register a volunteer on blockchain."""
    metadata_uri: str = Field(..., description="IPFS URI for profile metadata")


class CreateTaskRequest(BaseModel):
    """Request to create a task on blockchain."""
    task_id: str = Field(..., description="Unique task ID")
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    request_type: str = Field(..., description="Type of help needed")
    priority: str = Field(..., description="Priority level")
    content_hash: str = Field(..., description="IPFS hash of details")
    ttl_seconds: int = Field(default=3600, ge=300, le=604800)


class DonateRequest(BaseModel):
    """Request to donate to a task."""
    task_id: str = Field(..., description="Task ID to donate to")
    amount_ether: float = Field(..., gt=0, description="Amount in ETH/MATIC")


class IdentityResponse(BaseModel):
    """Volunteer identity information."""
    tokenId: int
    reputationScore: int
    tasksCompleted: int
    tasksReported: int
    falseReports: int
    registeredAt: int
    isVerified: bool
    trustLevel: int


class TaskTrustResponse(BaseModel):
    """Task verification status."""
    status: str
    statusCode: int
    verificationScore: int
    disputeScore: int
    verifierCount: int
    isVerified: bool


class PoolStatusResponse(BaseModel):
    """Donation pool status."""
    totalAmount: int
    claimedAmount: int
    signatureCount: int
    requiredSignatures: int
    gpsVerified: bool
    canRelease: bool


class MeshStatsResponse(BaseModel):
    """Mesh network node statistics."""
    packetsRelayed: int
    uptimeMinutes: int
    messagesDelivered: int
    balance: float
    totalEarned: float


class TransactionResponse(BaseModel):
    """Response with transaction hash."""
    success: bool
    transactionHash: str
    message: str = ""


# ===== Helper to get blockchain service =====

def get_blockchain_service():
    """Get blockchain service, handling initialization errors."""
    try:
        from blockchain import get_blockchain
        return get_blockchain()
    except RuntimeError as e:
        raise HTTPException(
            status_code=503, 
            detail=f"Blockchain service not available: {str(e)}"
        )


# ===== Volunteer Identity Endpoints =====

@router.post(
    "/register",
    response_model=TransactionResponse,
    summary="Register as a volunteer on blockchain"
)
async def register_volunteer(request: RegisterVolunteerRequest):
    """Register a new volunteer and mint their Soul-Bound NFT."""
    try:
        bc = get_blockchain_service()
        tx_hash = bc.register_volunteer(request.metadata_uri)
        return TransactionResponse(
            success=True,
            transactionHash=tx_hash,
            message="Registration submitted. Wait for confirmation."
        )
    except Exception as e:
        logger.error(f"Registration failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/identity/{address}",
    response_model=IdentityResponse,
    summary="Get volunteer identity"
)
async def get_identity(address: str):
    """Get identity information for a wallet address."""
    try:
        bc = get_blockchain_service()
        identity = bc.get_identity(address)
        identity["trustLevel"] = bc.get_trust_level(address)
        return IdentityResponse(**identity)
    except Exception as e:
        logger.error(f"Failed to get identity: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/trust-level/{address}",
    summary="Get trust level for an address"
)
async def get_trust_level(address: str):
    """Get trust level (0-4) for a wallet address."""
    try:
        bc = get_blockchain_service()
        level = bc.get_trust_level(address)
        level_names = ["Untrusted", "Low Trust", "Neutral", "Trusted", "Highly Trusted"]
        return {
            "address": address,
            "trustLevel": level,
            "trustLevelName": level_names[level] if level < len(level_names) else "Unknown"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ===== Task Escrow Endpoints =====

@router.post(
    "/task",
    response_model=TransactionResponse,
    summary="Create task on blockchain"
)
async def create_blockchain_task(request: CreateTaskRequest):
    """Create a help request task on the blockchain."""
    try:
        bc = get_blockchain_service()
        tx_hash = bc.create_task(
            request.task_id,
            request.latitude,
            request.longitude,
            request.request_type,
            request.priority,
            request.content_hash,
            request.ttl_seconds
        )
        return TransactionResponse(
            success=True,
            transactionHash=tx_hash,
            message="Task creation submitted."
        )
    except Exception as e:
        logger.error(f"Task creation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/task/{task_id}/verify",
    response_model=TransactionResponse,
    summary="Verify a task"
)
async def verify_task(task_id: str):
    """Verify that a help request is real (requires trust level 2+)."""
    try:
        bc = get_blockchain_service()
        tx_hash = bc.verify_task(task_id)
        return TransactionResponse(
            success=True,
            transactionHash=tx_hash,
            message="Verification submitted."
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/task/{task_id}/accept",
    response_model=TransactionResponse,
    summary="Accept a verified task"
)
async def accept_task(task_id: str):
    """Accept a verified task as a volunteer."""
    try:
        bc = get_blockchain_service()
        tx_hash = bc.accept_task(task_id)
        return TransactionResponse(
            success=True,
            transactionHash=tx_hash,
            message="Task acceptance submitted."
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/task/{task_id}/complete",
    response_model=TransactionResponse,
    summary="Mark task as completed"
)
async def complete_task(task_id: str):
    """Mark a task as completed (only creator can call)."""
    try:
        bc = get_blockchain_service()
        tx_hash = bc.complete_task(task_id)
        return TransactionResponse(
            success=True,
            transactionHash=tx_hash,
            message="Task completion submitted."
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/task/{task_id}/status",
    response_model=TaskTrustResponse,
    summary="Get task verification status"
)
async def get_task_status(task_id: str):
    """Get the verification status of a task."""
    try:
        bc = get_blockchain_service()
        return TaskTrustResponse(**bc.get_task_trust_info(task_id))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ===== Donation Endpoints =====

@router.post(
    "/donate",
    response_model=TransactionResponse,
    summary="Donate to a task"
)
async def donate(request: DonateRequest):
    """Donate funds to a verified task."""
    try:
        bc = get_blockchain_service()
        from web3 import Web3
        amount_wei = Web3.to_wei(request.amount_ether, 'ether')
        tx_hash = bc.donate(request.task_id, amount_wei)
        return TransactionResponse(
            success=True,
            transactionHash=tx_hash,
            message=f"Donation of {request.amount_ether} ETH submitted."
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/donation/{task_id}/sign",
    response_model=TransactionResponse,
    summary="Sign for fund release"
)
async def sign_release(task_id: str):
    """Sign to approve fund release (requires trust level 3+)."""
    try:
        bc = get_blockchain_service()
        tx_hash = bc.sign_release(task_id)
        return TransactionResponse(
            success=True,
            transactionHash=tx_hash,
            message="Signature submitted."
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/donation/{task_id}/status",
    response_model=PoolStatusResponse,
    summary="Get donation pool status"
)
async def get_donation_status(task_id: str):
    """Get the status of a donation pool."""
    try:
        bc = get_blockchain_service()
        return PoolStatusResponse(**bc.get_pool_status(task_id))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ===== Mesh Incentive Endpoints =====

@router.get(
    "/mesh/{address}/stats",
    response_model=MeshStatsResponse,
    summary="Get mesh network stats"
)
async def get_mesh_stats(address: str):
    """Get P2P mesh network statistics for a node."""
    try:
        bc = get_blockchain_service()
        stats = bc.get_mesh_stats(address)
        return MeshStatsResponse(
            packetsRelayed=stats["packetsRelayed"],
            uptimeMinutes=stats["uptimeMinutes"],
            messagesDelivered=stats["messagesDelivered"],
            balance=float(stats["balance"]),
            totalEarned=float(stats["totalEarned"])
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/mesh/{address}/balance",
    summary="Get MESH token balance"
)
async def get_mesh_balance(address: str):
    """Get MESH token balance for an address."""
    try:
        bc = get_blockchain_service()
        balance = bc.get_mesh_balance(address)
        return {
            "address": address,
            "balance": balance,
            "token": "MESH"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
