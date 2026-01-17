"""
wallet_api.py - FastAPI Router for Wallet Operations

This module provides REST API endpoints for wallet management:
- Create new wallets
- Import from mnemonic
- Sign messages
- Check balances
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import Optional, List
import logging

from wallet import (
    get_wallet_manager, 
    WalletManager, 
    WalletInfo,
    verify_signature
)
from security import get_api_key

logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/wallet", tags=["Wallet"])


# ═══════════════════════════════════════════════════════════════════════════
# REQUEST/RESPONSE MODELS
# ═══════════════════════════════════════════════════════════════════════════

class CreateWalletRequest(BaseModel):
    """Request to create a new wallet."""
    password: str = Field(..., min_length=8, description="Encryption password (min 8 chars)")
    name: str = Field(default="default", description="Wallet name")


class CreateWalletResponse(BaseModel):
    """Response with new wallet details."""
    address: str
    mnemonic: str = Field(..., description="⚠️ Save this! Shown only once!")
    name: str
    message: str = "Wallet created successfully. SAVE YOUR MNEMONIC!"


class ImportMnemonicRequest(BaseModel):
    """Request to import wallet from mnemonic."""
    mnemonic: str = Field(..., description="12 or 24 word mnemonic phrase")
    password: str = Field(..., min_length=8)
    name: str = Field(default="imported")


class ImportPrivateKeyRequest(BaseModel):
    """Request to import wallet from private key."""
    private_key: str = Field(..., description="Hex private key")
    password: str = Field(..., min_length=8)
    name: str = Field(default="imported")


class UnlockWalletRequest(BaseModel):
    """Request to unlock a wallet."""
    address: str
    password: str


class SignMessageRequest(BaseModel):
    """Request to sign a message."""
    message: str = Field(..., min_length=1)


class SignMessageResponse(BaseModel):
    """Response with signature."""
    message: str
    signature: str
    signer: str
    message_hash: str


class VerifySignatureRequest(BaseModel):
    """Request to verify a signature."""
    message: str
    signature: str
    address: str


class WalletInfoResponse(BaseModel):
    """Wallet information response."""
    address: str
    name: str
    created_at: str
    derivation_path: str
    is_encrypted: bool
    is_unlocked: bool = False


class BalanceResponse(BaseModel):
    """Balance response."""
    address: str
    balance_wei: int
    balance_eth: float


# ═══════════════════════════════════════════════════════════════════════════
# HELPER
# ═══════════════════════════════════════════════════════════════════════════

def get_manager() -> WalletManager:
    """Get wallet manager instance."""
    return get_wallet_manager()


# ═══════════════════════════════════════════════════════════════════════════
# ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════

@router.post("/create", response_model=CreateWalletResponse)
async def create_wallet(
    request: CreateWalletRequest,
    api_key: str = Depends(get_api_key)
):
    """
    Create a new HD wallet.
    
    ⚠️ **WARNING**: The mnemonic phrase is shown only ONCE!
    Save it securely - it cannot be recovered.
    """
    try:
        manager = get_manager()
        mnemonic, address = manager.create_wallet(
            password=request.password,
            name=request.name
        )
        
        return CreateWalletResponse(
            address=address,
            mnemonic=mnemonic,
            name=request.name
        )
        
    except Exception as e:
        logger.error(f"Failed to create wallet: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/import/mnemonic")
async def import_from_mnemonic(
    request: ImportMnemonicRequest,
    api_key: str = Depends(get_api_key)
):
    """Import a wallet from mnemonic phrase."""
    try:
        manager = get_manager()
        address = manager.import_from_mnemonic(
            mnemonic_phrase=request.mnemonic,
            password=request.password,
            name=request.name
        )
        
        return {
            "success": True,
            "address": address,
            "name": request.name,
            "message": "Wallet imported successfully"
        }
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to import wallet: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/import/private-key")
async def import_from_private_key(
    request: ImportPrivateKeyRequest,
    api_key: str = Depends(get_api_key)
):
    """Import a wallet from private key."""
    try:
        manager = get_manager()
        address = manager.import_from_private_key(
            private_key=request.private_key,
            password=request.password,
            name=request.name
        )
        
        return {
            "success": True,
            "address": address,
            "name": request.name,
            "message": "Wallet imported successfully"
        }
        
    except Exception as e:
        logger.error(f"Failed to import wallet: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/unlock")
async def unlock_wallet(
    request: UnlockWalletRequest,
    api_key: str = Depends(get_api_key)
):
    """Unlock an existing wallet."""
    try:
        manager = get_manager()
        address = manager.load_wallet(
            address=request.address,
            password=request.password
        )
        
        return {
            "success": True,
            "address": address,
            "message": "Wallet unlocked"
        }
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to unlock wallet: {e}")
        raise HTTPException(status_code=500, detail="Invalid password or wallet not found")


@router.post("/lock")
async def lock_wallet(api_key: str = Depends(get_api_key)):
    """Lock the current wallet (clear from memory)."""
    manager = get_manager()
    manager.lock_wallet()
    
    return {
        "success": True,
        "message": "Wallet locked"
    }


@router.get("/list", response_model=List[WalletInfoResponse])
async def list_wallets(api_key: str = Depends(get_api_key)):
    """List all stored wallets."""
    manager = get_manager()
    wallets = manager.list_wallets()
    active = manager.active_address
    
    return [
        WalletInfoResponse(
            address=w.address,
            name=w.name,
            created_at=w.created_at,
            derivation_path=w.derivation_path,
            is_encrypted=w.is_encrypted,
            is_unlocked=(active and active.lower() == w.address.lower())
        )
        for w in wallets
    ]


@router.get("/active")
async def get_active_wallet(api_key: str = Depends(get_api_key)):
    """Get the currently active (unlocked) wallet."""
    manager = get_manager()
    
    if not manager.is_unlocked:
        return {
            "unlocked": False,
            "message": "No wallet is currently unlocked"
        }
    
    wallet = manager.get_active_wallet()
    
    return {
        "unlocked": True,
        "address": wallet.address if wallet else manager.active_address,
        "name": wallet.name if wallet else "unknown"
    }


@router.delete("/{address}")
async def delete_wallet(
    address: str,
    api_key: str = Depends(get_api_key)
):
    """Delete a stored wallet."""
    manager = get_manager()
    deleted = manager.delete_wallet(address)
    
    if deleted:
        return {"success": True, "message": f"Wallet {address} deleted"}
    else:
        raise HTTPException(status_code=404, detail="Wallet not found")


@router.post("/sign-message", response_model=SignMessageResponse)
async def sign_message(
    request: SignMessageRequest,
    api_key: str = Depends(get_api_key)
):
    """
    Sign a message with the active wallet.
    
    Requires an unlocked wallet.
    """
    manager = get_manager()
    
    if not manager.is_unlocked:
        raise HTTPException(
            status_code=400, 
            detail="No wallet unlocked. Call /wallet/unlock first."
        )
    
    try:
        result = manager.sign_message(request.message)
        return SignMessageResponse(**result)
        
    except Exception as e:
        logger.error(f"Failed to sign message: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/verify-signature")
async def verify_signature_endpoint(request: VerifySignatureRequest):
    """
    Verify a message signature.
    
    This endpoint is public (no API key required).
    """
    try:
        is_valid = verify_signature(
            message=request.message,
            signature=request.signature,
            address=request.address
        )
        
        return {
            "valid": is_valid,
            "message": request.message,
            "signer": request.address
        }
        
    except Exception as e:
        return {
            "valid": False,
            "error": str(e)
        }


@router.get("/balance/{address}", response_model=BalanceResponse)
async def get_balance(address: str):
    """
    Get ETH balance for an address.
    
    This endpoint is public (no API key required).
    """
    try:
        from blockchain import get_blockchain
        bc = get_blockchain()
        
        balance_wei = bc.web3.eth.get_balance(address)
        balance_eth = float(bc.web3.from_wei(balance_wei, 'ether'))
        
        return BalanceResponse(
            address=address,
            balance_wei=balance_wei,
            balance_eth=balance_eth
        )
        
    except RuntimeError:
        # Blockchain not initialized
        raise HTTPException(
            status_code=503, 
            detail="Blockchain service not available"
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/nonce/{address}")
async def get_nonce(address: str):
    """Get transaction nonce for an address."""
    try:
        from blockchain import get_blockchain
        bc = get_blockchain()
        
        nonce = bc.web3.eth.get_transaction_count(address)
        
        return {
            "address": address,
            "nonce": nonce
        }
        
    except RuntimeError:
        raise HTTPException(
            status_code=503, 
            detail="Blockchain service not available"
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
