// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "./VolunteerIdentity.sol";

/**
 * @title TaskEscrow
 * @notice Manages help request lifecycle with verification and escrow
 * @dev Tracks tasks from creation → verification → completion
 * 
 * Flow:
 * 1. Victim creates request → Status: PENDING
 * 2. Trusted users verify → Status: VERIFIED (when score >= threshold)
 * 3. Volunteer accepts → Status: IN_PROGRESS
 * 4. Victim confirms delivery → Status: COMPLETED
 * 5. Reputation rewards distributed
 */
contract TaskEscrow {
    
    // ===== Referenced Contracts =====
    
    VolunteerIdentity public identityContract;
    
    // ===== Enums =====
    
    enum TaskStatus {
        PENDING,      // Just created, awaiting verification
        VERIFIED,     // Confirmed real by trusted users
        IN_PROGRESS,  // Volunteer accepted
        COMPLETED,    // Aid delivered, confirmed
        DISPUTED,     // Conflicting reports
        CANCELLED,    // Marked as fake or expired
        EXPIRED       // TTL exceeded
    }
    
    // ===== Data Structures =====
    
    struct Task {
        bytes32 id;                   // Unique task ID (hash of UUID)
        address creator;              // Who needs help
        address assignedVolunteer;    // Who's helping
        
        // Location (scaled by 1e6 for precision)
        int256 latitude;
        int256 longitude;
        
        string requestType;           // "medical", "rescue", etc.
        string priority;              // "critical", "high", etc.
        string contentHash;           // IPFS hash of details
        
        TaskStatus status;
        uint256 createdAt;
        uint256 expiresAt;
        
        // Verification tracking
        uint256 verificationScore;    // Sum of verifier trust levels
        uint256 disputeScore;         // Reports that it's fake
    }
    
    // ===== State Variables =====
    
    mapping(bytes32 => Task) public tasks;
    mapping(bytes32 => address[]) public taskVerifiers;    // Who verified
    mapping(bytes32 => address[]) public taskDisputers;    // Who disputed
    mapping(bytes32 => mapping(address => bool)) public hasVerified;
    mapping(bytes32 => mapping(address => bool)) public hasDisputed;
    
    bytes32[] public taskIds;
    
    // Configuration
    uint256 public constant VERIFICATION_THRESHOLD = 10;  // Score needed
    uint8 public constant MIN_VERIFIER_TRUST = 2;         // Min trust level to verify
    
    // Reward points
    uint256 public constant VERIFICATION_REWARD = 5;      // Points for verifying
    uint256 public constant TASK_COMPLETION_REWARD = 50;  // Base completion reward
    uint256 public constant CRITICAL_BONUS = 50;          // Extra for critical tasks
    uint256 public constant CREATOR_REWARD = 10;          // Reward for honest reporting
    
    // ===== Events =====
    
    event TaskCreated(
        bytes32 indexed id, 
        address indexed creator, 
        string requestType,
        string priority
    );
    event TaskVerified(
        bytes32 indexed id, 
        address indexed verifier, 
        uint256 totalScore
    );
    event TaskDisputed(bytes32 indexed id, address indexed disputer);
    event TaskAccepted(bytes32 indexed id, address indexed volunteer);
    event TaskCompleted(
        bytes32 indexed id, 
        address indexed volunteer, 
        uint256 rewardPoints
    );
    event TaskCancelled(bytes32 indexed id, string reason);
    event TaskExpired(bytes32 indexed id);
    event StatusChanged(bytes32 indexed id, TaskStatus newStatus);
    
    // ===== Constructor =====
    
    constructor(address _identityContract) {
        identityContract = VolunteerIdentity(_identityContract);
    }
    
    // ===== Task Creation =====
    
    /**
     * @notice Create a new help request
     * @param _id Unique ID (hash of off-chain UUID)
     * @param _latitude Location latitude (scaled by 1e6)
     * @param _longitude Location longitude (scaled by 1e6)
     * @param _requestType Type of help needed
     * @param _priority Priority level
     * @param _contentHash IPFS hash of detailed description
     * @param _ttlSeconds Time-to-live in seconds
     */
    function createTask(
        bytes32 _id,
        int256 _latitude,
        int256 _longitude,
        string calldata _requestType,
        string calldata _priority,
        string calldata _contentHash,
        uint256 _ttlSeconds
    ) external {
        require(tasks[_id].createdAt == 0, "Task already exists");
        require(_ttlSeconds >= 300 && _ttlSeconds <= 604800, "TTL must be 5min-7days");
        
        // Creator must be registered
        require(
            identityContract.isRegistered(msg.sender),
            "Must register first"
        );
        
        tasks[_id] = Task({
            id: _id,
            creator: msg.sender,
            assignedVolunteer: address(0),
            latitude: _latitude,
            longitude: _longitude,
            requestType: _requestType,
            priority: _priority,
            contentHash: _contentHash,
            status: TaskStatus.PENDING,
            createdAt: block.timestamp,
            expiresAt: block.timestamp + _ttlSeconds,
            verificationScore: 0,
            disputeScore: 0
        });
        
        taskIds.push(_id);
        
        // Update creator's task count
        identityContract.incrementTasksReported(msg.sender);
        
        emit TaskCreated(_id, msg.sender, _requestType, _priority);
        emit StatusChanged(_id, TaskStatus.PENDING);
    }
    
    // ===== Verification Functions =====
    
    /**
     * @notice Verify a help request is real
     * @param _id Task ID to verify
     * @dev Only users with trust level >= 2 can verify
     */
    function verifyTask(bytes32 _id) external {
        Task storage task = tasks[_id];
        require(task.createdAt != 0, "Task does not exist");
        require(task.status == TaskStatus.PENDING, "Task not pending");
        require(task.creator != msg.sender, "Cannot verify own request");
        require(!hasVerified[_id][msg.sender], "Already verified");
        require(block.timestamp < task.expiresAt, "Task expired");
        
        // Check verifier's trust level
        uint8 trustLevel = identityContract.getTrustLevel(msg.sender);
        require(trustLevel >= MIN_VERIFIER_TRUST, "Insufficient trust level");
        
        // Record verification
        taskVerifiers[_id].push(msg.sender);
        hasVerified[_id][msg.sender] = true;
        task.verificationScore += trustLevel;
        
        // If threshold reached, mark as verified
        if (task.verificationScore >= VERIFICATION_THRESHOLD) {
            task.status = TaskStatus.VERIFIED;
            emit StatusChanged(_id, TaskStatus.VERIFIED);
        }
        
        // Reward verifier
        identityContract.updateReputation(msg.sender, int256(VERIFICATION_REWARD));
        
        emit TaskVerified(_id, msg.sender, task.verificationScore);
    }
    
    /**
     * @notice Dispute a request as fake
     * @param _id Task ID to dispute
     */
    function disputeTask(bytes32 _id) external {
        Task storage task = tasks[_id];
        require(task.createdAt != 0, "Task does not exist");
        require(
            task.status == TaskStatus.PENDING || 
            task.status == TaskStatus.VERIFIED,
            "Cannot dispute this task"
        );
        require(!hasDisputed[_id][msg.sender], "Already disputed");
        
        uint8 trustLevel = identityContract.getTrustLevel(msg.sender);
        require(trustLevel >= MIN_VERIFIER_TRUST, "Insufficient trust level");
        
        // Record dispute
        taskDisputers[_id].push(msg.sender);
        hasDisputed[_id][msg.sender] = true;
        task.disputeScore += trustLevel;
        
        // If disputes exceed verifications, mark as disputed
        if (task.disputeScore > task.verificationScore) {
            task.status = TaskStatus.DISPUTED;
            emit StatusChanged(_id, TaskStatus.DISPUTED);
        }
        
        emit TaskDisputed(_id, msg.sender);
    }
    
    // ===== Task Lifecycle =====
    
    /**
     * @notice Volunteer accepts a verified task
     * @param _id Task ID to accept
     */
    function acceptTask(bytes32 _id) external {
        Task storage task = tasks[_id];
        require(task.createdAt != 0, "Task does not exist");
        require(task.status == TaskStatus.VERIFIED, "Task not verified");
        require(task.assignedVolunteer == address(0), "Already assigned");
        require(block.timestamp < task.expiresAt, "Task expired");
        require(
            identityContract.isRegistered(msg.sender),
            "Must register first"
        );
        
        task.assignedVolunteer = msg.sender;
        task.status = TaskStatus.IN_PROGRESS;
        
        emit TaskAccepted(_id, msg.sender);
        emit StatusChanged(_id, TaskStatus.IN_PROGRESS);
    }
    
    /**
     * @notice Mark task as completed (only creator can confirm)
     * @param _id Task ID to complete
     */
    function completeTask(bytes32 _id) external {
        Task storage task = tasks[_id];
        require(task.createdAt != 0, "Task does not exist");
        require(task.status == TaskStatus.IN_PROGRESS, "Task not in progress");
        require(msg.sender == task.creator, "Only creator can confirm");
        
        task.status = TaskStatus.COMPLETED;
        
        // Calculate reward
        uint256 rewardPoints = TASK_COMPLETION_REWARD;
        if (keccak256(bytes(task.priority)) == keccak256(bytes("critical"))) {
            rewardPoints += CRITICAL_BONUS;
        }
        
        // Reward volunteer
        identityContract.updateReputation(
            task.assignedVolunteer, 
            int256(rewardPoints)
        );
        identityContract.incrementTasksCompleted(task.assignedVolunteer);
        
        // Small reward for honest reporter
        identityContract.updateReputation(task.creator, int256(CREATOR_REWARD));
        
        emit TaskCompleted(_id, task.assignedVolunteer, rewardPoints);
        emit StatusChanged(_id, TaskStatus.COMPLETED);
    }
    
    /**
     * @notice Cancel a disputed task and penalize creator
     * @param _id Task ID to cancel
     * @dev Can only be called by owner or high-trust users
     */
    function cancelFalseTask(bytes32 _id) external {
        Task storage task = tasks[_id];
        require(task.createdAt != 0, "Task does not exist");
        require(task.status == TaskStatus.DISPUTED, "Task not disputed");
        
        // Must be high trust to cancel
        require(
            identityContract.getTrustLevel(msg.sender) >= 3,
            "Need trust level 3+"
        );
        
        task.status = TaskStatus.CANCELLED;
        
        // Penalize creator for false report
        identityContract.recordFalseReport(task.creator);
        
        emit TaskCancelled(_id, "False report");
        emit StatusChanged(_id, TaskStatus.CANCELLED);
    }
    
    /**
     * @notice Mark expired tasks
     * @param _id Task ID to expire
     */
    function expireTask(bytes32 _id) external {
        Task storage task = tasks[_id];
        require(task.createdAt != 0, "Task does not exist");
        require(block.timestamp >= task.expiresAt, "Not expired yet");
        require(
            task.status == TaskStatus.PENDING ||
            task.status == TaskStatus.VERIFIED,
            "Cannot expire this task"
        );
        
        task.status = TaskStatus.EXPIRED;
        emit TaskExpired(_id);
        emit StatusChanged(_id, TaskStatus.EXPIRED);
    }
    
    // ===== View Functions =====
    
    /**
     * @notice Get task verification status
     * @param _id Task ID
     */
    function getTaskTrustInfo(bytes32 _id) external view returns (
        TaskStatus status,
        uint256 verificationScore,
        uint256 disputeScore,
        uint256 verifierCount,
        bool isVerified
    ) {
        Task storage task = tasks[_id];
        return (
            task.status,
            task.verificationScore,
            task.disputeScore,
            taskVerifiers[_id].length,
            task.status == TaskStatus.VERIFIED || 
            task.status == TaskStatus.IN_PROGRESS ||
            task.status == TaskStatus.COMPLETED
        );
    }
    
    /**
     * @notice Get full task details
     * @param _id Task ID
     */
    function getTask(bytes32 _id) external view returns (
        address creator,
        address assignedVolunteer,
        int256 latitude,
        int256 longitude,
        string memory requestType,
        string memory priority,
        TaskStatus status,
        uint256 createdAt,
        uint256 expiresAt
    ) {
        Task storage task = tasks[_id];
        return (
            task.creator,
            task.assignedVolunteer,
            task.latitude,
            task.longitude,
            task.requestType,
            task.priority,
            task.status,
            task.createdAt,
            task.expiresAt
        );
    }
    
    /**
     * @notice Get list of verifiers for a task
     * @param _id Task ID
     */
    function getTaskVerifiers(bytes32 _id) external view returns (address[] memory) {
        return taskVerifiers[_id];
    }
    
    /**
     * @notice Get total number of tasks
     */
    function getTotalTasks() external view returns (uint256) {
        return taskIds.length;
    }
    
    /**
     * @notice Check if task exists
     * @param _id Task ID
     */
    function taskExists(bytes32 _id) external view returns (bool) {
        return tasks[_id].createdAt != 0;
    }
}
