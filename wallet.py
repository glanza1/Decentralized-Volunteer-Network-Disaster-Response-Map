"""
wallet.py - Wallet Management for Disaster Response System

This module provides secure wallet management including:
- HD wallet creation (BIP-39 mnemonic)
- Wallet import from mnemonic
- Encrypted private key storage
- Message and transaction signing

Security:
- Private keys are encrypted with AES-256-GCM
- Mnemonics are shown only once during creation
- Keys are derived using BIP-44 standard path
"""

import os
import json
import hashlib
import secrets
import logging
from pathlib import Path
from typing import Optional, Dict, Any, Tuple
from dataclasses import dataclass
from datetime import datetime

from mnemonic import Mnemonic
from eth_account import Account
from eth_account.hdaccount import generate_mnemonic, key_from_seed, seed_from_mnemonic
from web3 import Web3

# Cryptography for key encryption
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes

logger = logging.getLogger(__name__)

# Configuration
WALLET_DIR = Path(__file__).parent / ".wallets"
DEFAULT_DERIVATION_PATH = "m/44'/60'/0'/0/0"  # Ethereum standard
PBKDF2_ITERATIONS = 100000


@dataclass
class WalletInfo:
    """Information about a wallet (without sensitive data)."""
    address: str
    name: str
    created_at: str
    derivation_path: str
    is_encrypted: bool


class WalletManager:
    """
    Manages Ethereum wallets with HD derivation and encrypted storage.
    
    Features:
    - Create new wallets with BIP-39 mnemonic
    - Import wallets from existing mnemonic
    - Encrypt private keys with password
    - Sign messages and transactions
    """
    
    def __init__(self, wallet_dir: Optional[Path] = None):
        """
        Initialize wallet manager.
        
        Args:
            wallet_dir: Directory for storing encrypted wallets
        """
        self.wallet_dir = wallet_dir or WALLET_DIR
        self.wallet_dir.mkdir(parents=True, exist_ok=True)
        
        # Currently active wallet
        self._active_wallet: Optional[Account] = None
        self._active_address: Optional[str] = None
        
        # Web3 instance for utilities
        self.web3 = Web3()
        
        # Enable HD wallet features
        Account.enable_unaudited_hdwallet_features()
        
        logger.info(f"WalletManager initialized, wallet dir: {self.wallet_dir}")
    
    def create_wallet(
        self,
        password: str,
        name: str = "default",
        derivation_path: str = DEFAULT_DERIVATION_PATH
    ) -> Tuple[str, str]:
        """
        Create a new HD wallet with mnemonic.
        
        Args:
            password: Password for encrypting the private key
            name: Wallet name for identification
            derivation_path: BIP-44 derivation path
            
        Returns:
            Tuple of (mnemonic phrase, wallet address)
            
        Warning:
            The mnemonic is shown only ONCE. Save it securely!
        """
        # Generate mnemonic (BIP-39)
        mnemo = Mnemonic("english")
        mnemonic_phrase = mnemo.generate(strength=128)  # 12 words
        
        # Derive account from mnemonic
        account = Account.from_mnemonic(mnemonic_phrase, account_path=derivation_path)
        
        # Encrypt and save
        self._save_wallet(account, password, name, derivation_path)
        
        # Set as active
        self._active_wallet = account
        self._active_address = account.address
        
        logger.info(f"Created new wallet: {account.address}")
        
        return mnemonic_phrase, account.address
    
    def import_from_mnemonic(
        self,
        mnemonic_phrase: str,
        password: str,
        name: str = "imported",
        derivation_path: str = DEFAULT_DERIVATION_PATH
    ) -> str:
        """
        Import a wallet from existing mnemonic phrase.
        
        Args:
            mnemonic_phrase: 12 or 24 word mnemonic
            password: Password for encrypting the private key
            name: Wallet name for identification
            derivation_path: BIP-44 derivation path
            
        Returns:
            Wallet address
        """
        # Validate mnemonic
        mnemo = Mnemonic("english")
        if not mnemo.check(mnemonic_phrase):
            raise ValueError("Invalid mnemonic phrase")
        
        # Derive account
        account = Account.from_mnemonic(mnemonic_phrase, account_path=derivation_path)
        
        # Encrypt and save
        self._save_wallet(account, password, name, derivation_path)
        
        # Set as active
        self._active_wallet = account
        self._active_address = account.address
        
        logger.info(f"Imported wallet: {account.address}")
        
        return account.address
    
    def import_from_private_key(
        self,
        private_key: str,
        password: str,
        name: str = "imported"
    ) -> str:
        """
        Import a wallet from private key.
        
        Args:
            private_key: Hex private key (with or without 0x prefix)
            password: Password for encryption
            name: Wallet name
            
        Returns:
            Wallet address
        """
        account = Account.from_key(private_key)
        
        # Save without derivation path (not HD)
        self._save_wallet(account, password, name, None)
        
        self._active_wallet = account
        self._active_address = account.address
        
        logger.info(f"Imported wallet from private key: {account.address}")
        
        return account.address
    
    def load_wallet(self, address: str, password: str) -> str:
        """
        Load and unlock an existing wallet.
        
        Args:
            address: Wallet address to load
            password: Password to decrypt
            
        Returns:
            Wallet address if successful
        """
        wallet_path = self._get_wallet_path(address)
        
        if not wallet_path.exists():
            raise ValueError(f"Wallet not found: {address}")
        
        with open(wallet_path, 'r') as f:
            wallet_data = json.load(f)
        
        # Decrypt private key
        private_key = self._decrypt_key(
            encrypted_key=bytes.fromhex(wallet_data["encrypted_key"]),
            salt=bytes.fromhex(wallet_data["salt"]),
            nonce=bytes.fromhex(wallet_data["nonce"]),
            password=password
        )
        
        account = Account.from_key(private_key)
        
        if account.address.lower() != address.lower():
            raise ValueError("Decryption failed: address mismatch")
        
        self._active_wallet = account
        self._active_address = account.address
        
        logger.info(f"Loaded wallet: {account.address}")
        
        return account.address
    
    def lock_wallet(self) -> None:
        """Lock the current wallet (clear from memory)."""
        self._active_wallet = None
        self._active_address = None
        logger.info("Wallet locked")
    
    def list_wallets(self) -> list[WalletInfo]:
        """List all stored wallets."""
        wallets = []
        
        for wallet_file in self.wallet_dir.glob("*.json"):
            try:
                with open(wallet_file, 'r') as f:
                    data = json.load(f)
                
                wallets.append(WalletInfo(
                    address=data["address"],
                    name=data.get("name", "unnamed"),
                    created_at=data.get("created_at", "unknown"),
                    derivation_path=data.get("derivation_path", "N/A"),
                    is_encrypted=True
                ))
            except Exception as e:
                logger.warning(f"Failed to read wallet file {wallet_file}: {e}")
        
        return wallets
    
    def delete_wallet(self, address: str) -> bool:
        """Delete a wallet file."""
        wallet_path = self._get_wallet_path(address)
        
        if wallet_path.exists():
            wallet_path.unlink()
            
            # Clear if it was active
            if self._active_address and self._active_address.lower() == address.lower():
                self.lock_wallet()
            
            logger.info(f"Deleted wallet: {address}")
            return True
        
        return False
    
    def sign_message(self, message: str) -> Dict[str, str]:
        """
        Sign a message with the active wallet.
        
        Args:
            message: Message to sign
            
        Returns:
            Dictionary with signature details
        """
        if not self._active_wallet:
            raise RuntimeError("No wallet loaded. Call load_wallet() first.")
        
        # Create signable message
        from eth_account.messages import encode_defunct
        signable = encode_defunct(text=message)
        
        # Sign
        signed = self._active_wallet.sign_message(signable)
        
        return {
            "message": message,
            "signature": signed.signature.hex(),
            "signer": self._active_address,
            "message_hash": signed.message_hash.hex()
        }
    
    def sign_transaction(self, tx_dict: dict) -> Dict[str, Any]:
        """
        Sign a transaction with the active wallet.
        
        Args:
            tx_dict: Transaction dictionary
            
        Returns:
            Signed transaction details
        """
        if not self._active_wallet:
            raise RuntimeError("No wallet loaded. Call load_wallet() first.")
        
        signed = self._active_wallet.sign_transaction(tx_dict)
        
        return {
            "raw_transaction": signed.raw_transaction.hex(),
            "hash": signed.hash.hex(),
            "r": hex(signed.r),
            "s": hex(signed.s),
            "v": signed.v
        }
    
    def get_active_wallet(self) -> Optional[WalletInfo]:
        """Get info about the currently active wallet."""
        if not self._active_address:
            return None
        
        wallet_path = self._get_wallet_path(self._active_address)
        
        if wallet_path.exists():
            with open(wallet_path, 'r') as f:
                data = json.load(f)
            
            return WalletInfo(
                address=self._active_address,
                name=data.get("name", "unnamed"),
                created_at=data.get("created_at", "unknown"),
                derivation_path=data.get("derivation_path", "N/A"),
                is_encrypted=True
            )
        
        return WalletInfo(
            address=self._active_address,
            name="in-memory",
            created_at="N/A",
            derivation_path="N/A",
            is_encrypted=False
        )
    
    @property
    def active_address(self) -> Optional[str]:
        """Get the active wallet address."""
        return self._active_address
    
    @property
    def is_unlocked(self) -> bool:
        """Check if a wallet is currently unlocked."""
        return self._active_wallet is not None
    
    # ===== Private Methods =====
    
    def _save_wallet(
        self,
        account: Account,
        password: str,
        name: str,
        derivation_path: Optional[str]
    ) -> None:
        """Save wallet with encrypted private key."""
        # Encrypt the private key
        encrypted, salt, nonce = self._encrypt_key(account.key.hex(), password)
        
        wallet_data = {
            "address": account.address,
            "name": name,
            "created_at": datetime.utcnow().isoformat(),
            "derivation_path": derivation_path,
            "encrypted_key": encrypted.hex(),
            "salt": salt.hex(),
            "nonce": nonce.hex(),
            "version": 1
        }
        
        wallet_path = self._get_wallet_path(account.address)
        
        with open(wallet_path, 'w') as f:
            json.dump(wallet_data, f, indent=2)
        
        # Set restrictive permissions
        wallet_path.chmod(0o600)
    
    def _get_wallet_path(self, address: str) -> Path:
        """Get the file path for a wallet."""
        # Normalize address
        address = address.lower().replace("0x", "")
        return self.wallet_dir / f"{address}.json"
    
    def _encrypt_key(self, private_key: str, password: str) -> Tuple[bytes, bytes, bytes]:
        """
        Encrypt a private key using AES-256-GCM.
        
        Returns:
            Tuple of (encrypted_data, salt, nonce)
        """
        # Generate salt and derive key
        salt = secrets.token_bytes(16)
        key = self._derive_key(password, salt)
        
        # Encrypt with AES-GCM
        nonce = secrets.token_bytes(12)
        aesgcm = AESGCM(key)
        
        # Remove 0x prefix if present
        if private_key.startswith("0x"):
            private_key = private_key[2:]
        
        encrypted = aesgcm.encrypt(nonce, private_key.encode(), None)
        
        return encrypted, salt, nonce
    
    def _decrypt_key(
        self,
        encrypted_key: bytes,
        salt: bytes,
        nonce: bytes,
        password: str
    ) -> str:
        """Decrypt a private key."""
        key = self._derive_key(password, salt)
        aesgcm = AESGCM(key)
        
        decrypted = aesgcm.decrypt(nonce, encrypted_key, None)
        return decrypted.decode()
    
    def _derive_key(self, password: str, salt: bytes) -> bytes:
        """Derive encryption key from password using PBKDF2."""
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=PBKDF2_ITERATIONS,
        )
        return kdf.derive(password.encode())


# ===== Utility Functions =====

def verify_signature(message: str, signature: str, address: str) -> bool:
    """
    Verify a message signature.
    
    Args:
        message: Original message
        signature: Hex signature
        address: Expected signer address
        
    Returns:
        True if signature is valid
    """
    from eth_account.messages import encode_defunct
    
    signable = encode_defunct(text=message)
    recovered = Account.recover_message(signable, signature=signature)
    
    return recovered.lower() == address.lower()


def generate_random_wallet() -> Tuple[str, str]:
    """
    Generate a random wallet without saving.
    
    Returns:
        Tuple of (private_key, address)
    """
    account = Account.create()
    return account.key.hex(), account.address


# ===== Global Instance =====

_wallet_manager: Optional[WalletManager] = None


def get_wallet_manager() -> WalletManager:
    """Get or create the global wallet manager."""
    global _wallet_manager
    
    if _wallet_manager is None:
        _wallet_manager = WalletManager()
    
    return _wallet_manager


def init_wallet_manager(wallet_dir: Optional[Path] = None) -> WalletManager:
    """Initialize the global wallet manager."""
    global _wallet_manager
    _wallet_manager = WalletManager(wallet_dir)
    return _wallet_manager
