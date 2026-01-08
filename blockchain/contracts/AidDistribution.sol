// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "./TaskEscrow.sol";
import "./VolunteerIdentity.sol";

/**
 * @title AidDistribution
 * @notice Multi-signature fund release with verification conditions
 * @dev Handles transparent donation management for disaster relief
 * 
 * Key Features:
 * - Donations locked until conditions met
 * - Requires N-of-M trusted signatures to release
 * - GPS verification integration
 * - Full audit trail on-chain
 */
contract AidDistribution {
    
    // ===== Referenced Contracts =====
    
    TaskEscrow public taskEscrow;
    VolunteerIdentity public identityContract;
    
    // ===== Data Structures =====
    
    struct DonationPool {
        bytes32 taskId;           // Linked help request
        uint256 totalAmount;      // Total donated (in wei)
        uint256 claimedAmount;    // Already distributed
        bool isActive;
        
        // Multi-sig requirements
        uint256 requiredSignatures;
        uint256 signatureCount;
        
        // Verification conditions
        bool gpsVerified;         // Location confirmed
        bool deliveryConfirmed;   // Physical delivery verified
    }
    
    // ===== State Variables =====
    
    mapping(bytes32 => DonationPool) public pools;
    mapping(bytes32 => address[]) public poolSigners;
    mapping(bytes32 => mapping(address => bool)) public hasSigned;
    mapping(bytes32 => address[]) public donors;
    mapping(bytes32 => mapping(address => uint256)) public donorAmounts;
    
    bytes32[] public activePoolIds;
    
    // Configuration
    uint256 public constant DEFAULT_REQUIRED_SIGNATURES = 3;
    uint8 public constant MIN_SIGNER_TRUST = 3;  // Trust level 3+ required
    
    // ===== Events =====
    
    event DonationReceived(
        bytes32 indexed taskId, 
        address indexed donor, 
        uint256 amount
    );
    event PoolCreated(bytes32 indexed taskId, uint256 requiredSignatures);
    event SignatureAdded(
        bytes32 indexed taskId, 
        address indexed signer,
        uint256 currentCount
    );
    event GPSVerified(bytes32 indexed taskId, int256 lat, int256 lng);
    event FundsReleased(
        bytes32 indexed taskId, 
        address indexed recipient, 
        uint256 amount
    );
    event DonationRefunded(
        bytes32 indexed taskId, 
        address indexed donor, 
        uint256 amount
    );
    
    // ===== Constructor =====
    
    constructor(address _taskEscrow, address _identityContract) {
        taskEscrow = TaskEscrow(_taskEscrow);
        identityContract = VolunteerIdentity(_identityContract);
    }
    
    // ===== Donation Functions =====
    
    /**
     * @notice Donate to a specific help request
     * @param _taskId Task ID to donate to
     */
    function donate(bytes32 _taskId) external payable {
        require(msg.value > 0, "Must send funds");
        require(taskEscrow.taskExists(_taskId), "Task does not exist");
        
        // Verify task is in valid state
        (TaskEscrow.TaskStatus status,,,,) = taskEscrow.getTaskTrustInfo(_taskId);
        require(
            status == TaskEscrow.TaskStatus.VERIFIED ||
            status == TaskEscrow.TaskStatus.IN_PROGRESS,
            "Task not accepting donations"
        );
        
        DonationPool storage pool = pools[_taskId];
        
        // Create pool if doesn't exist
        if (!pool.isActive) {
            pool.taskId = _taskId;
            pool.isActive = true;
            pool.requiredSignatures = DEFAULT_REQUIRED_SIGNATURES;
            activePoolIds.push(_taskId);
            emit PoolCreated(_taskId, DEFAULT_REQUIRED_SIGNATURES);
        }
        
        // Track donor
        if (donorAmounts[_taskId][msg.sender] == 0) {
            donors[_taskId].push(msg.sender);
        }
        
        pool.totalAmount += msg.value;
        donorAmounts[_taskId][msg.sender] += msg.value;
        
        emit DonationReceived(_taskId, msg.sender, msg.value);
    }
    
    // ===== Multi-Sig Functions =====
    
    /**
     * @notice Add signature for fund release
     * @param _taskId Pool to sign for
     * @dev Only high-trust volunteers can sign
     */
    function signRelease(bytes32 _taskId) external {
        DonationPool storage pool = pools[_taskId];
        require(pool.isActive, "Pool not active");
        require(!hasSigned[_taskId][msg.sender], "Already signed");
        
        // Must be trusted volunteer (level 3+)
        uint8 trustLevel = identityContract.getTrustLevel(msg.sender);
        require(trustLevel >= MIN_SIGNER_TRUST, "Need trust level 3+");
        
        poolSigners[_taskId].push(msg.sender);
        hasSigned[_taskId][msg.sender] = true;
        pool.signatureCount++;
        
        emit SignatureAdded(_taskId, msg.sender, pool.signatureCount);
    }
    
    // ===== Verification Functions =====
    
    /**
     * @notice Submit GPS proof of presence at location
     * @param _taskId Task ID
     * @param _latitude GPS latitude (scaled by 1e6)
     * @param _longitude GPS longitude (scaled by 1e6)
     * @dev Only assigned volunteer can submit
     */
    function submitGPSProof(
        bytes32 _taskId,
        int256 _latitude,
        int256 _longitude
    ) external {
        DonationPool storage pool = pools[_taskId];
        require(pool.isActive, "Pool not active");
        
        // Only assigned volunteer can verify GPS
        (
            ,
            address assignedVolunteer,
            int256 taskLat,
            int256 taskLng,
            ,
            ,
            ,
            ,
        ) = taskEscrow.getTask(_taskId);
        
        require(msg.sender == assignedVolunteer, "Only assigned volunteer");
        
        // Simple proximity check (within ~100m)
        // In production, use Chainlink oracle for GPS verification
        int256 latDiff = _latitude > taskLat ? 
            _latitude - taskLat : taskLat - _latitude;
        int256 lngDiff = _longitude > taskLng ? 
            _longitude - taskLng : taskLng - _longitude;
        
        require(latDiff < 1000 && lngDiff < 1000, "Location mismatch");
        
        pool.gpsVerified = true;
        emit GPSVerified(_taskId, _latitude, _longitude);
    }
    
    // ===== Fund Release =====
    
    /**
     * @notice Release funds to victim after all conditions met
     * @param _taskId Task ID
     */
    function releaseFunds(bytes32 _taskId) external {
        DonationPool storage pool = pools[_taskId];
        require(pool.isActive, "Pool not active");
        require(
            pool.signatureCount >= pool.requiredSignatures, 
            "Need more signatures"
        );
        require(pool.gpsVerified, "GPS not verified");
        
        // Check task is completed
        (TaskEscrow.TaskStatus status,,,,) = taskEscrow.getTaskTrustInfo(_taskId);
        require(
            status == TaskEscrow.TaskStatus.COMPLETED, 
            "Task not completed"
        );
        
        uint256 amountToRelease = pool.totalAmount - pool.claimedAmount;
        require(amountToRelease > 0, "No funds to release");
        
        // Get victim's address
        (address creator,,,,,,,,) = taskEscrow.getTask(_taskId);
        
        pool.claimedAmount = pool.totalAmount;
        
        // Transfer funds
        (bool success, ) = creator.call{value: amountToRelease}("");
        require(success, "Transfer failed");
        
        emit FundsReleased(_taskId, creator, amountToRelease);
    }
    
    /**
     * @notice Refund donations if task cancelled
     * @param _taskId Task ID
     */
    function refundDonations(bytes32 _taskId) external {
        DonationPool storage pool = pools[_taskId];
        require(pool.isActive, "Pool not active");
        
        // Task must be cancelled or expired
        (TaskEscrow.TaskStatus status,,,,) = taskEscrow.getTaskTrustInfo(_taskId);
        require(
            status == TaskEscrow.TaskStatus.CANCELLED ||
            status == TaskEscrow.TaskStatus.EXPIRED,
            "Task not cancelled/expired"
        );
        
        // Refund each donor
        for (uint256 i = 0; i < donors[_taskId].length; i++) {
            address donor = donors[_taskId][i];
            uint256 amount = donorAmounts[_taskId][donor];
            
            if (amount > 0) {
                donorAmounts[_taskId][donor] = 0;
                (bool success, ) = donor.call{value: amount}("");
                if (success) {
                    emit DonationRefunded(_taskId, donor, amount);
                }
            }
        }
        
        pool.isActive = false;
    }
    
    // ===== View Functions =====
    
    /**
     * @notice Get pool status
     * @param _taskId Task ID
     */
    function getPoolStatus(bytes32 _taskId) external view returns (
        uint256 totalAmount,
        uint256 claimedAmount,
        uint256 signatureCount,
        uint256 requiredSignatures,
        bool gpsVerified,
        bool canRelease
    ) {
        DonationPool storage pool = pools[_taskId];
        (TaskEscrow.TaskStatus status,,,,) = taskEscrow.getTaskTrustInfo(_taskId);
        
        return (
            pool.totalAmount,
            pool.claimedAmount,
            pool.signatureCount,
            pool.requiredSignatures,
            pool.gpsVerified,
            pool.signatureCount >= pool.requiredSignatures &&
            pool.gpsVerified &&
            status == TaskEscrow.TaskStatus.COMPLETED
        );
    }
    
    /**
     * @notice Get signers for a pool
     * @param _taskId Task ID
     */
    function getPoolSigners(bytes32 _taskId) external view returns (address[] memory) {
        return poolSigners[_taskId];
    }
    
    /**
     * @notice Get donors for a pool
     * @param _taskId Task ID
     */
    function getPoolDonors(bytes32 _taskId) external view returns (address[] memory) {
        return donors[_taskId];
    }
    
    /**
     * @notice Get donation amount by donor
     * @param _taskId Task ID
     * @param _donor Donor address
     */
    function getDonationAmount(
        bytes32 _taskId, 
        address _donor
    ) external view returns (uint256) {
        return donorAmounts[_taskId][_donor];
    }
    
    /**
     * @notice Get contract balance
     */
    function getContractBalance() external view returns (uint256) {
        return address(this).balance;
    }
    
    // ===== Fallback =====
    
    receive() external payable {
        revert("Use donate() function");
    }
}
