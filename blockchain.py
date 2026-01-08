"""
blockchain.py - Web3 Integration for Disaster Response Smart Contracts

This module provides a Python interface for interacting with the blockchain
smart contracts deployed for the disaster response system.

Usage:
    from blockchain import init_blockchain, get_blockchain
    
    # Initialize once at startup
    init_blockchain(rpc_url="http://localhost:8545", private_key="...")
    
    # Use the service
    bc = get_blockchain()
    bc.register_volunteer("ipfs://metadata")
"""

from web3 import Web3
from eth_account import Account
from typing import Optional, Dict, Any, List
import json
import os
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class BlockchainService:
    """
    Service for interacting with disaster response smart contracts.
    
    Provides methods for:
    - VolunteerIdentity: Registration, reputation, trust levels
    - TaskEscrow: Task creation, verification, completion
    - AidDistribution: Donations, signatures, fund release
    - MeshIncentive: P2P network rewards
    """
    
    def __init__(
        self, 
        rpc_url: str, 
        private_key: Optional[str] = None,
        contracts_dir: Optional[str] = None
    ):
        """
        Initialize blockchain connection.
        
        Args:
            rpc_url: Blockchain RPC endpoint (e.g., http://localhost:8545)
            private_key: Wallet private key for signing transactions
            contracts_dir: Path to contract deployment JSONs
        """
        self.web3 = Web3(Web3.HTTPProvider(rpc_url))
        self.private_key = private_key
        self.account = Account.from_key(private_key) if private_key else None
        
        # Default contracts directory
        if contracts_dir is None:
            contracts_dir = Path(__file__).parent / "blockchain" / "deployments"
        self.contracts_dir = Path(contracts_dir)
        
        # Contract instances
        self.contracts: Dict[str, Any] = {}
        
        # Try to load contracts
        self._load_contracts()
        
        logger.info(f"BlockchainService initialized, connected: {self.web3.is_connected()}")
    
    def _load_contracts(self) -> None:
        """Load deployed contract instances from JSON files."""
        contract_names = [
            "VolunteerIdentity",
            "TaskEscrow", 
            "AidDistribution",
            "MeshIncentive"
        ]
        
        for name in contract_names:
            json_path = self.contracts_dir / f"{name}.json"
            if json_path.exists():
                try:
                    with open(json_path) as f:
                        data = json.load(f)
                    
                    # Parse ABI if it's a string
                    abi = data["abi"]
                    if isinstance(abi, str):
                        abi = json.loads(abi)
                    
                    self.contracts[name] = self.web3.eth.contract(
                        address=Web3.to_checksum_address(data["address"]),
                        abi=abi
                    )
                    logger.info(f"Loaded contract {name} at {data['address']}")
                except Exception as e:
                    logger.warning(f"Failed to load contract {name}: {e}")
            else:
                logger.warning(f"Contract deployment not found: {json_path}")
    
    def _get_contract(self, name: str):
        """Get a contract instance by name."""
        if name not in self.contracts:
            raise RuntimeError(f"Contract {name} not loaded. Deploy contracts first.")
        return self.contracts[name]
    
    def _build_and_send_tx(self, contract_func) -> str:
        """Build, sign, and send a transaction."""
        if not self.account:
            raise RuntimeError("Private key required for transactions")
        
        tx = contract_func.build_transaction({
            "from": self.account.address,
            "nonce": self.web3.eth.get_transaction_count(self.account.address),
            "gas": 500000,
            "gasPrice": self.web3.eth.gas_price,
        })
        
        signed = self.web3.eth.account.sign_transaction(tx, self.private_key)
        tx_hash = self.web3.eth.send_raw_transaction(signed.raw_transaction)
        
        logger.info(f"Transaction sent: {tx_hash.hex()}")
        return tx_hash.hex()
    
    # ===== VolunteerIdentity Functions =====
    
    def register_volunteer(self, metadata_uri: str) -> str:
        """
        Register a new volunteer.
        
        Args:
            metadata_uri: IPFS URI for profile metadata
            
        Returns:
            Transaction hash
        """
        contract = self._get_contract("VolunteerIdentity")
        func = contract.functions.register(metadata_uri)
        return self._build_and_send_tx(func)
    
    def get_trust_level(self, address: str) -> int:
        """
        Get user's trust level (0-4).
        
        Args:
            address: User's wallet address
            
        Returns:
            Trust level (0=Untrusted, 4=Highly Trusted)
        """
        contract = self._get_contract("VolunteerIdentity")
        return contract.functions.getTrustLevel(
            Web3.to_checksum_address(address)
        ).call()
    
    def get_identity(self, address: str) -> Dict[str, Any]:
        """
        Get full identity info for a user.
        
        Args:
            address: User's wallet address
            
        Returns:
            Dictionary with identity fields
        """
        contract = self._get_contract("VolunteerIdentity")
        result = contract.functions.getIdentity(
            Web3.to_checksum_address(address)
        ).call()
        
        return {
            "tokenId": result[0],
            "reputationScore": result[1],
            "tasksCompleted": result[2],
            "tasksReported": result[3],
            "falseReports": result[4],
            "registeredAt": result[5],
            "isVerified": result[6]
        }
    
    def is_registered(self, address: str) -> bool:
        """Check if an address is registered."""
        contract = self._get_contract("VolunteerIdentity")
        return contract.functions.isRegistered(
            Web3.to_checksum_address(address)
        ).call()
    
    # ===== TaskEscrow Functions =====
    
    def create_task(
        self, 
        task_id: str, 
        latitude: float, 
        longitude: float,
        request_type: str, 
        priority: str, 
        content_hash: str,
        ttl_seconds: int = 3600
    ) -> str:
        """
        Create a new help request task on blockchain.
        
        Args:
            task_id: Unique task ID (will be hashed)
            latitude: GPS latitude
            longitude: GPS longitude
            request_type: Type of help needed
            priority: Priority level
            content_hash: IPFS hash of full details
            ttl_seconds: Time-to-live in seconds
            
        Returns:
            Transaction hash
        """
        contract = self._get_contract("TaskEscrow")
        task_id_bytes = Web3.keccak(text=task_id)
        
        func = contract.functions.createTask(
            task_id_bytes,
            int(latitude * 1e6),  # Scale for precision
            int(longitude * 1e6),
            request_type,
            priority,
            content_hash,
            ttl_seconds
        )
        return self._build_and_send_tx(func)
    
    def verify_task(self, task_id: str) -> str:
        """
        Verify a task as real.
        
        Args:
            task_id: Task ID to verify
            
        Returns:
            Transaction hash
        """
        contract = self._get_contract("TaskEscrow")
        task_id_bytes = Web3.keccak(text=task_id)
        func = contract.functions.verifyTask(task_id_bytes)
        return self._build_and_send_tx(func)
    
    def accept_task(self, task_id: str) -> str:
        """Accept a verified task as volunteer."""
        contract = self._get_contract("TaskEscrow")
        task_id_bytes = Web3.keccak(text=task_id)
        func = contract.functions.acceptTask(task_id_bytes)
        return self._build_and_send_tx(func)
    
    def complete_task(self, task_id: str) -> str:
        """Mark a task as completed (only creator can call)."""
        contract = self._get_contract("TaskEscrow")
        task_id_bytes = Web3.keccak(text=task_id)
        func = contract.functions.completeTask(task_id_bytes)
        return self._build_and_send_tx(func)
    
    def get_task_trust_info(self, task_id: str) -> Dict[str, Any]:
        """
        Get verification status of a task.
        
        Args:
            task_id: Task ID
            
        Returns:
            Dictionary with trust info
        """
        contract = self._get_contract("TaskEscrow")
        task_id_bytes = Web3.keccak(text=task_id)
        result = contract.functions.getTaskTrustInfo(task_id_bytes).call()
        
        status_names = [
            "PENDING", "VERIFIED", "IN_PROGRESS", 
            "COMPLETED", "DISPUTED", "CANCELLED", "EXPIRED"
        ]
        
        return {
            "status": status_names[result[0]] if result[0] < len(status_names) else "UNKNOWN",
            "statusCode": result[0],
            "verificationScore": result[1],
            "disputeScore": result[2],
            "verifierCount": result[3],
            "isVerified": result[4]
        }
    
    def task_exists(self, task_id: str) -> bool:
        """Check if a task exists."""
        contract = self._get_contract("TaskEscrow")
        task_id_bytes = Web3.keccak(text=task_id)
        return contract.functions.taskExists(task_id_bytes).call()
    
    def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get task status (alias for get_task_trust_info)."""
        try:
            return self.get_task_trust_info(task_id)
        except Exception:
            return None
    
    # ===== AidDistribution Functions =====
    
    def donate(self, task_id: str, amount_wei: int) -> str:
        """
        Donate to a task.
        
        Args:
            task_id: Task ID to donate to
            amount_wei: Amount in wei
            
        Returns:
            Transaction hash
        """
        contract = self._get_contract("AidDistribution")
        task_id_bytes = Web3.keccak(text=task_id)
        
        tx = contract.functions.donate(task_id_bytes).build_transaction({
            "from": self.account.address,
            "value": amount_wei,
            "nonce": self.web3.eth.get_transaction_count(self.account.address),
            "gas": 200000,
            "gasPrice": self.web3.eth.gas_price,
        })
        
        signed = self.web3.eth.account.sign_transaction(tx, self.private_key)
        tx_hash = self.web3.eth.send_raw_transaction(signed.raw_transaction)
        return tx_hash.hex()
    
    def sign_release(self, task_id: str) -> str:
        """Sign for fund release (requires trust level 3+)."""
        contract = self._get_contract("AidDistribution")
        task_id_bytes = Web3.keccak(text=task_id)
        func = contract.functions.signRelease(task_id_bytes)
        return self._build_and_send_tx(func)
    
    def get_pool_status(self, task_id: str) -> Dict[str, Any]:
        """Get donation pool status."""
        contract = self._get_contract("AidDistribution")
        task_id_bytes = Web3.keccak(text=task_id)
        result = contract.functions.getPoolStatus(task_id_bytes).call()
        
        return {
            "totalAmount": result[0],
            "claimedAmount": result[1],
            "signatureCount": result[2],
            "requiredSignatures": result[3],
            "gpsVerified": result[4],
            "canRelease": result[5]
        }
    
    # ===== MeshIncentive Functions =====
    
    def record_relay(self, node_address: str, packet_count: int) -> str:
        """Record packets relayed by a node (operator only)."""
        contract = self._get_contract("MeshIncentive")
        func = contract.functions.recordRelay(
            Web3.to_checksum_address(node_address), 
            packet_count
        )
        return self._build_and_send_tx(func)
    
    def record_uptime(self, node_address: str, minutes: int) -> str:
        """Record uptime for a node (operator only)."""
        contract = self._get_contract("MeshIncentive")
        func = contract.functions.recordUptime(
            Web3.to_checksum_address(node_address), 
            minutes
        )
        return self._build_and_send_tx(func)
    
    def record_delivery(self, node_address: str, message_id: str) -> str:
        """Record successful message delivery."""
        contract = self._get_contract("MeshIncentive")
        message_id_bytes = Web3.keccak(text=message_id)
        func = contract.functions.recordDelivery(
            Web3.to_checksum_address(node_address),
            message_id_bytes
        )
        return self._build_and_send_tx(func)
    
    def get_mesh_stats(self, node_address: str) -> Dict[str, Any]:
        """Get mesh network stats and rewards for a node."""
        contract = self._get_contract("MeshIncentive")
        result = contract.functions.getNodeStats(
            Web3.to_checksum_address(node_address)
        ).call()
        
        return {
            "packetsRelayed": result[0],
            "uptimeMinutes": result[1],
            "messagesDelivered": result[2],
            "balanceWei": result[3],
            "balance": Web3.from_wei(result[3], 'ether'),
            "totalEarnedWei": result[4],
            "totalEarned": Web3.from_wei(result[4], 'ether')
        }
    
    def get_mesh_balance(self, node_address: str) -> float:
        """Get MESH token balance."""
        contract = self._get_contract("MeshIncentive")
        balance = contract.functions.balanceOf(
            Web3.to_checksum_address(node_address)
        ).call()
        return float(Web3.from_wei(balance, 'ether'))


# ===== Global Instance =====

_blockchain_service: Optional[BlockchainService] = None


def init_blockchain(
    rpc_url: str = "http://localhost:8545",
    private_key: Optional[str] = None,
    contracts_dir: Optional[str] = None
) -> BlockchainService:
    """
    Initialize the global blockchain service.
    
    Args:
        rpc_url: Blockchain RPC endpoint
        private_key: Wallet private key (optional for read-only)
        contracts_dir: Path to contract deployments
        
    Returns:
        BlockchainService instance
    """
    global _blockchain_service
    _blockchain_service = BlockchainService(rpc_url, private_key, contracts_dir)
    return _blockchain_service


def get_blockchain() -> BlockchainService:
    """Get the global blockchain service instance."""
    if _blockchain_service is None:
        raise RuntimeError(
            "Blockchain service not initialized. Call init_blockchain() first."
        )
    return _blockchain_service
