// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/token/ERC20/ERC20.sol";
import "@openzeppelin/contracts/access/Ownable.sol";

/**
 * @title MeshIncentive
 * @notice ERC-20 token rewards for P2P mesh network participation
 * @dev Rewards users who keep their nodes active and relay data
 * 
 * Reward Actions:
 * - Relay data packets for other nodes
 * - Stay online during disasters
 * - Successfully deliver messages
 */
contract MeshIncentive is ERC20, Ownable {
    
    // ===== Data Structures =====
    
    struct NodeStats {
        uint256 packetsRelayed;      // Total packets forwarded
        uint256 uptimeMinutes;       // Total uptime tracked
        uint256 messagesDelivered;   // Successful deliveries
        uint256 lastCheckin;         // Last activity timestamp
        uint256 totalRewardsEarned;  // Lifetime rewards
    }
    
    // ===== State Variables =====
    
    mapping(address => NodeStats) public nodeStats;
    
    // Reward rates (in token base units, 18 decimals)
    uint256 public relayReward = 1 * 10**18;      // 1 MESH per packet
    uint256 public uptimeReward = 10 * 10**18;    // 10 MESH per hour
    uint256 public deliveryReward = 5 * 10**18;   // 5 MESH per message
    
    // Operators authorized to report node activities
    mapping(address => bool) public operators;
    
    // Total supply cap (optional, 0 = unlimited)
    uint256 public maxSupply;
    
    // ===== Events =====
    
    event PacketsRelayed(
        address indexed node, 
        uint256 count, 
        uint256 reward
    );
    event UptimeRecorded(
        address indexed node, 
        uint256 _minutes, 
        uint256 reward
    );
    event MessageDelivered(
        address indexed node, 
        bytes32 messageId, 
        uint256 reward
    );
    event OperatorUpdated(address indexed operator, bool authorized);
    event RewardRatesUpdated(uint256 relay, uint256 uptime, uint256 delivery);
    
    // ===== Constructor =====
    
    constructor() ERC20("MeshNetworkCredit", "MESH") Ownable(msg.sender) {
        operators[msg.sender] = true;
        maxSupply = 1000000000 * 10**18; // 1 billion max supply
    }
    
    // ===== Modifiers =====
    
    modifier onlyOperator() {
        require(operators[msg.sender], "Not an operator");
        _;
    }
    
    // ===== Node Reward Functions =====
    
    /**
     * @notice Record packets relayed by a node
     * @param _node Node address that relayed packets
     * @param _packetCount Number of packets relayed
     * @dev Called by backend when node reports relay activity
     */
    function recordRelay(
        address _node, 
        uint256 _packetCount
    ) external onlyOperator {
        require(_packetCount > 0, "Must relay at least 1 packet");
        
        NodeStats storage stats = nodeStats[_node];
        stats.packetsRelayed += _packetCount;
        stats.lastCheckin = block.timestamp;
        
        uint256 reward = _packetCount * relayReward;
        _mintWithCap(_node, reward);
        stats.totalRewardsEarned += reward;
        
        emit PacketsRelayed(_node, _packetCount, reward);
    }
    
    /**
     * @notice Record uptime for a node
     * @param _node Node address
     * @param _minutes Minutes of uptime
     * @dev Called periodically by backend
     */
    function recordUptime(
        address _node, 
        uint256 _minutes
    ) external onlyOperator {
        require(_minutes > 0, "Must record at least 1 minute");
        
        NodeStats storage stats = nodeStats[_node];
        stats.uptimeMinutes += _minutes;
        stats.lastCheckin = block.timestamp;
        
        // Reward per hour (60 minutes)
        uint256 hours_ = _minutes / 60;
        uint256 reward = hours_ * uptimeReward;
        
        if (reward > 0) {
            _mintWithCap(_node, reward);
            stats.totalRewardsEarned += reward;
            emit UptimeRecorded(_node, _minutes, reward);
        }
    }
    
    /**
     * @notice Record successful message delivery
     * @param _node Node that delivered the message
     * @param _messageId Unique message identifier
     */
    function recordDelivery(
        address _node, 
        bytes32 _messageId
    ) external onlyOperator {
        NodeStats storage stats = nodeStats[_node];
        stats.messagesDelivered++;
        stats.lastCheckin = block.timestamp;
        
        uint256 reward = deliveryReward;
        _mintWithCap(_node, reward);
        stats.totalRewardsEarned += reward;
        
        emit MessageDelivered(_node, _messageId, reward);
    }
    
    /**
     * @notice Batch record multiple activities
     * @param _node Node address
     * @param _packets Packets relayed
     * @param _minutes Uptime minutes
     * @param _deliveries Message deliveries
     */
    function recordBatch(
        address _node,
        uint256 _packets,
        uint256 _minutes,
        uint256 _deliveries
    ) external onlyOperator {
        NodeStats storage stats = nodeStats[_node];
        stats.lastCheckin = block.timestamp;
        
        uint256 totalReward = 0;
        
        if (_packets > 0) {
            stats.packetsRelayed += _packets;
            totalReward += _packets * relayReward;
        }
        
        if (_minutes >= 60) {
            stats.uptimeMinutes += _minutes;
            totalReward += (_minutes / 60) * uptimeReward;
        }
        
        if (_deliveries > 0) {
            stats.messagesDelivered += _deliveries;
            totalReward += _deliveries * deliveryReward;
        }
        
        if (totalReward > 0) {
            _mintWithCap(_node, totalReward);
            stats.totalRewardsEarned += totalReward;
        }
    }
    
    // ===== View Functions =====
    
    /**
     * @notice Get node statistics
     * @param _node Node address
     */
    function getNodeStats(address _node) external view returns (
        uint256 packetsRelayed,
        uint256 uptimeMinutes,
        uint256 messagesDelivered,
        uint256 balance,
        uint256 totalEarned
    ) {
        NodeStats storage stats = nodeStats[_node];
        return (
            stats.packetsRelayed,
            stats.uptimeMinutes,
            stats.messagesDelivered,
            balanceOf(_node),
            stats.totalRewardsEarned
        );
    }
    
    /**
     * @notice Check if node was active recently
     * @param _node Node address
     * @param _withinSeconds Time window in seconds
     */
    function isNodeActive(
        address _node, 
        uint256 _withinSeconds
    ) external view returns (bool) {
        return block.timestamp - nodeStats[_node].lastCheckin < _withinSeconds;
    }
    
    /**
     * @notice Get remaining mintable supply
     */
    function remainingMintable() external view returns (uint256) {
        if (maxSupply == 0) return type(uint256).max;
        return maxSupply > totalSupply() ? maxSupply - totalSupply() : 0;
    }
    
    // ===== Admin Functions =====
    
    /**
     * @notice Set operator authorization
     * @param _operator Address to update
     * @param _authorized Whether to authorize or revoke
     */
    function setOperator(
        address _operator, 
        bool _authorized
    ) external onlyOwner {
        operators[_operator] = _authorized;
        emit OperatorUpdated(_operator, _authorized);
    }
    
    /**
     * @notice Update reward rates
     * @param _relayReward New relay reward
     * @param _uptimeReward New uptime reward (per hour)
     * @param _deliveryReward New delivery reward
     */
    function setRewardRates(
        uint256 _relayReward,
        uint256 _uptimeReward,
        uint256 _deliveryReward
    ) external onlyOwner {
        relayReward = _relayReward;
        uptimeReward = _uptimeReward;
        deliveryReward = _deliveryReward;
        emit RewardRatesUpdated(_relayReward, _uptimeReward, _deliveryReward);
    }
    
    /**
     * @notice Update max supply cap
     * @param _maxSupply New max supply (0 = unlimited)
     */
    function setMaxSupply(uint256 _maxSupply) external onlyOwner {
        require(
            _maxSupply == 0 || _maxSupply >= totalSupply(), 
            "Cannot set below current supply"
        );
        maxSupply = _maxSupply;
    }
    
    // ===== Internal Functions =====
    
    /**
     * @dev Mint with supply cap check
     */
    function _mintWithCap(address _to, uint256 _amount) internal {
        if (maxSupply > 0) {
            uint256 remaining = maxSupply > totalSupply() ? 
                maxSupply - totalSupply() : 0;
            if (_amount > remaining) {
                _amount = remaining;
            }
        }
        
        if (_amount > 0) {
            _mint(_to, _amount);
        }
    }
}
