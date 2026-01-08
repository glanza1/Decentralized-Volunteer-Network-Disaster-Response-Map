// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/token/ERC721/ERC721.sol";
import "@openzeppelin/contracts/access/Ownable.sol";

/**
 * @title VolunteerIdentity
 * @notice Soul-Bound NFT for disaster response volunteers
 * @dev SBT cannot be transferred after minting, permanently linked to one wallet
 * 
 * Key Concepts:
 * - Soul-Bound Token (SBT): Cannot be transferred or sold
 * - Reputation Score: Trust level from 0-1000, affected by actions
 * - Badges: Achievement NFTs for milestones
 */
contract VolunteerIdentity is ERC721, Ownable {
    
    // ===== Data Structures =====
    
    struct Identity {
        uint256 tokenId;           // Unique NFT ID
        uint256 reputationScore;   // Trust score (0-1000)
        uint256 tasksCompleted;    // Help requests fulfilled
        uint256 tasksReported;     // Requests they submitted
        uint256 falseReports;      // Requests marked as fake
        uint256 registeredAt;      // Registration timestamp
        bool isVerified;           // Manual verification by authorities
        string metadataURI;        // IPFS link to profile data
    }
    
    // Badge types for achievements
    enum Badge {
        FIRST_RESPONDER,   // Responded to first help request
        LIFE_SAVER,        // Helped in 10+ critical situations
        TRUSTED_REPORTER,  // 50+ verified reports
        MESH_HERO          // Top P2P network contributor
    }
    
    // ===== State Variables =====
    
    mapping(address => Identity) public identities;
    mapping(uint256 => address) public tokenToAddress;
    mapping(address => mapping(Badge => bool)) public badges;
    
    // Contracts authorized to update reputation
    mapping(address => bool) public authorizedContracts;
    
    uint256 private _tokenIdCounter;
    
    // ===== Events =====
    
    event IdentityCreated(address indexed user, uint256 tokenId);
    event ReputationUpdated(address indexed user, int256 change, uint256 newScore);
    event BadgeEarned(address indexed user, Badge badge);
    event FalseReportPenalty(address indexed user, uint256 penalty);
    event ContractAuthorized(address indexed contractAddress, bool authorized);
    event VolunteerVerified(address indexed user);
    
    // ===== Constructor =====
    
    constructor() ERC721("DisasterVolunteer", "DVOL") Ownable(msg.sender) {}
    
    // ===== Modifiers =====
    
    modifier onlyAuthorized() {
        require(
            authorizedContracts[msg.sender] || msg.sender == owner(),
            "Not authorized"
        );
        _;
    }
    
    modifier onlyRegistered(address user) {
        require(identities[user].tokenId != 0, "User not registered");
        _;
    }
    
    // ===== Registration Functions =====
    
    /**
     * @notice Register as a volunteer - mints Soul-Bound NFT
     * @param _metadataURI IPFS URI containing profile metadata
     * @dev Cannot register twice. Token cannot be transferred.
     */
    function register(string calldata _metadataURI) external {
        require(identities[msg.sender].tokenId == 0, "Already registered");
        
        _tokenIdCounter++;
        uint256 newTokenId = _tokenIdCounter;
        
        _mint(msg.sender, newTokenId);
        
        identities[msg.sender] = Identity({
            tokenId: newTokenId,
            reputationScore: 100,  // Start with base score
            tasksCompleted: 0,
            tasksReported: 0,
            falseReports: 0,
            registeredAt: block.timestamp,
            isVerified: false,
            metadataURI: _metadataURI
        });
        
        tokenToAddress[newTokenId] = msg.sender;
        emit IdentityCreated(msg.sender, newTokenId);
    }
    
    // ===== Trust Level Functions =====
    
    /**
     * @notice Get trust level of a user (0-4 scale)
     * @param _user Address to check
     * @return Trust level:
     *   4 = Highly Trusted (800+)
     *   3 = Trusted (500-799)
     *   2 = Neutral (200-499)
     *   1 = Low Trust (50-199)
     *   0 = Untrusted/New (0-49)
     */
    function getTrustLevel(address _user) external view returns (uint8) {
        uint256 score = identities[_user].reputationScore;
        if (score >= 800) return 4;  // Highly Trusted
        if (score >= 500) return 3;  // Trusted
        if (score >= 200) return 2;  // Neutral
        if (score >= 50) return 1;   // Low Trust
        return 0;                     // Untrusted/New
    }
    
    /**
     * @notice Check if a user is registered
     * @param _user Address to check
     * @return True if user has a token
     */
    function isRegistered(address _user) external view returns (bool) {
        return identities[_user].tokenId != 0;
    }
    
    // ===== Reputation Functions =====
    
    /**
     * @notice Update reputation (called by authorized contracts like TaskEscrow)
     * @param _user User address to update
     * @param _change Amount to add (positive) or subtract (negative)
     * @return New reputation score
     */
    function updateReputation(
        address _user, 
        int256 _change
    ) external onlyAuthorized onlyRegistered(_user) returns (uint256) {
        Identity storage identity = identities[_user];
        
        if (_change > 0) {
            identity.reputationScore += uint256(_change);
            if (identity.reputationScore > 1000) {
                identity.reputationScore = 1000; // Cap at 1000
            }
        } else {
            uint256 penalty = uint256(-_change);
            if (penalty >= identity.reputationScore) {
                identity.reputationScore = 0;
            } else {
                identity.reputationScore -= penalty;
            }
        }
        
        emit ReputationUpdated(_user, _change, identity.reputationScore);
        return identity.reputationScore;
    }
    
    /**
     * @notice Increment task completion count
     * @param _user User who completed a task
     */
    function incrementTasksCompleted(address _user) 
        external 
        onlyAuthorized 
        onlyRegistered(_user) 
    {
        identities[_user].tasksCompleted++;
        
        // Auto-award badges for milestones
        if (identities[_user].tasksCompleted == 1) {
            _awardBadge(_user, Badge.FIRST_RESPONDER);
        }
        if (identities[_user].tasksCompleted == 10) {
            _awardBadge(_user, Badge.LIFE_SAVER);
        }
    }
    
    /**
     * @notice Increment tasks reported count
     * @param _user User who reported a task
     */
    function incrementTasksReported(address _user) 
        external 
        onlyAuthorized 
        onlyRegistered(_user) 
    {
        identities[_user].tasksReported++;
        
        // Auto-award badge for milestone
        if (identities[_user].tasksReported == 50) {
            _awardBadge(_user, Badge.TRUSTED_REPORTER);
        }
    }
    
    /**
     * @notice Record a false report penalty
     * @param _user User who submitted false report
     */
    function recordFalseReport(address _user) 
        external 
        onlyAuthorized 
        onlyRegistered(_user) 
    {
        identities[_user].falseReports++;
        
        // Heavy penalty for false reports (-100 points)
        Identity storage identity = identities[_user];
        if (identity.reputationScore >= 100) {
            identity.reputationScore -= 100;
        } else {
            identity.reputationScore = 0;
        }
        
        emit FalseReportPenalty(_user, 100);
        emit ReputationUpdated(_user, -100, identity.reputationScore);
    }
    
    // ===== Badge Functions =====
    
    /**
     * @notice Award a badge to a user
     * @param _user User to receive badge
     * @param _badge Badge type to award
     */
    function awardBadge(address _user, Badge _badge) 
        external 
        onlyAuthorized 
        onlyRegistered(_user) 
    {
        _awardBadge(_user, _badge);
    }
    
    function _awardBadge(address _user, Badge _badge) internal {
        if (!badges[_user][_badge]) {
            badges[_user][_badge] = true;
            emit BadgeEarned(_user, _badge);
        }
    }
    
    /**
     * @notice Check if user has a specific badge
     * @param _user User address
     * @param _badge Badge type
     * @return True if user has the badge
     */
    function hasBadge(address _user, Badge _badge) external view returns (bool) {
        return badges[_user][_badge];
    }
    
    // ===== Admin Functions =====
    
    /**
     * @notice Authorize a contract to update reputations
     * @param _contract Contract address
     * @param _authorized Whether to authorize or deauthorize
     */
    function setAuthorizedContract(address _contract, bool _authorized) 
        external 
        onlyOwner 
    {
        authorizedContracts[_contract] = _authorized;
        emit ContractAuthorized(_contract, _authorized);
    }
    
    /**
     * @notice Manually verify a volunteer (for authorities)
     * @param _user User to verify
     */
    function verifyVolunteer(address _user) 
        external 
        onlyOwner 
        onlyRegistered(_user) 
    {
        identities[_user].isVerified = true;
        emit VolunteerVerified(_user);
    }
    
    // ===== View Functions =====
    
    /**
     * @notice Get complete identity info for a user
     * @param _user User address
     * @return tokenId User's NFT token ID
     * @return reputationScore Current reputation score
     * @return tasksCompleted Number of tasks completed
     * @return tasksReported Number of tasks reported
     * @return falseReports Number of false reports
     * @return registeredAt Registration timestamp
     * @return isVerified Whether manually verified
     */
    function getIdentity(address _user) external view returns (
        uint256 tokenId,
        uint256 reputationScore,
        uint256 tasksCompleted,
        uint256 tasksReported,
        uint256 falseReports,
        uint256 registeredAt,
        bool isVerified
    ) {
        Identity storage identity = identities[_user];
        return (
            identity.tokenId,
            identity.reputationScore,
            identity.tasksCompleted,
            identity.tasksReported,
            identity.falseReports,
            identity.registeredAt,
            identity.isVerified
        );
    }
    
    /**
     * @notice Get total number of registered volunteers
     * @return Total count
     */
    function getTotalVolunteers() external view returns (uint256) {
        return _tokenIdCounter;
    }
    
    // ===== Soul-Bound: Disable Transfers =====
    
    /**
     * @dev Override to prevent transfers (Soul-Bound Token)
     * Only minting (from == address(0)) is allowed
     */
    function _update(
        address to,
        uint256 tokenId,
        address auth
    ) internal override returns (address) {
        address from = _ownerOf(tokenId);
        // Only allow minting (from == address(0)), block all transfers
        require(from == address(0), "Soul-bound: transfer disabled");
        return super._update(to, tokenId, auth);
    }
    
    /**
     * @dev Token URI returns the metadata URI from identity
     */
    function tokenURI(uint256 tokenId) public view override returns (string memory) {
        address owner = tokenToAddress[tokenId];
        require(owner != address(0), "Token does not exist");
        return identities[owner].metadataURI;
    }
}
