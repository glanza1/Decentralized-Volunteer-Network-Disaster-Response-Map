import 'package:flutter/material.dart';
import '../services/blockchain_service.dart';

/// Widget to display blockchain trust level badge
class TrustLevelBadge extends StatelessWidget {
  final int trustLevel;
  final bool showLabel;
  final double size;

  const TrustLevelBadge({
    super.key,
    required this.trustLevel,
    this.showLabel = true,
    this.size = 24,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: Color(BlockchainService.getTrustColor(trustLevel)).withOpacity(0.2),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(
          color: Color(BlockchainService.getTrustColor(trustLevel)),
          width: 1.5,
        ),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(
            _getIcon(trustLevel),
            color: Color(BlockchainService.getTrustColor(trustLevel)),
            size: size,
          ),
          if (showLabel) ...[
            const SizedBox(width: 4),
            Text(
              BlockchainService.getTrustName(trustLevel),
              style: TextStyle(
                color: Color(BlockchainService.getTrustColor(trustLevel)),
                fontWeight: FontWeight.bold,
                fontSize: size * 0.5,
              ),
            ),
          ],
        ],
      ),
    );
  }

  IconData _getIcon(int level) {
    switch (level) {
      case 4: return Icons.verified;
      case 3: return Icons.verified_user;
      case 2: return Icons.shield;
      case 1: return Icons.person;
      default: return Icons.person_outline;
    }
  }
}

/// Widget to show MESH token balance
class MeshBalanceWidget extends StatelessWidget {
  final double balance;
  final bool compact;

  const MeshBalanceWidget({
    super.key,
    required this.balance,
    this.compact = false,
  });

  @override
  Widget build(BuildContext context) {
    if (compact) {
      return Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          const Icon(Icons.token, color: Colors.purple, size: 16),
          const SizedBox(width: 4),
          Text(
            '${balance.toStringAsFixed(1)} MESH',
            style: const TextStyle(
              color: Colors.purple,
              fontWeight: FontWeight.bold,
              fontSize: 12,
            ),
          ),
        ],
      );
    }

    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        gradient: LinearGradient(
          colors: [Colors.purple.shade100, Colors.purple.shade50],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
        borderRadius: BorderRadius.circular(16),
      ),
      child: Column(
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Icon(Icons.token, color: Colors.purple.shade700, size: 28),
              const SizedBox(width: 8),
              Text(
                '${balance.toStringAsFixed(2)} MESH',
                style: TextStyle(
                  fontSize: 24,
                  fontWeight: FontWeight.bold,
                  color: Colors.purple.shade700,
                ),
              ),
            ],
          ),
          const SizedBox(height: 4),
          Text(
            'P2P Network Rewards',
            style: TextStyle(
              color: Colors.purple.shade400,
              fontSize: 12,
            ),
          ),
        ],
      ),
    );
  }
}

/// Widget to show blockchain verification status for a help request
class BlockchainVerifiedBadge extends StatelessWidget {
  final String status;
  final int verificationScore;

  const BlockchainVerifiedBadge({
    super.key,
    required this.status,
    required this.verificationScore,
  });

  @override
  Widget build(BuildContext context) {
    final isVerified = status == 'VERIFIED' || status == 'IN_PROGRESS' || status == 'COMPLETED';
    
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: isVerified ? Colors.green.withOpacity(0.1) : Colors.orange.withOpacity(0.1),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(
          color: isVerified ? Colors.green : Colors.orange,
          width: 1,
        ),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(
            isVerified ? Icons.verified : Icons.pending,
            color: isVerified ? Colors.green : Colors.orange,
            size: 14,
          ),
          const SizedBox(width: 4),
          Text(
            isVerified ? 'Verified' : 'Pending',
            style: TextStyle(
              color: isVerified ? Colors.green : Colors.orange,
              fontWeight: FontWeight.bold,
              fontSize: 11,
            ),
          ),
          if (verificationScore > 0) ...[
            const SizedBox(width: 4),
            Text(
              '($verificationScore)',
              style: TextStyle(
                color: isVerified ? Colors.green.shade300 : Colors.orange.shade300,
                fontSize: 10,
              ),
            ),
          ],
        ],
      ),
    );
  }
}

/// Reputation progress bar widget
class ReputationBar extends StatelessWidget {
  final int score;
  final int maxScore;
  final int trustLevel;

  const ReputationBar({
    super.key,
    required this.score,
    this.maxScore = 1000,
    required this.trustLevel,
  });

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            Text(
              'Reputation Score',
              style: TextStyle(
                color: Colors.grey.shade600,
                fontSize: 12,
              ),
            ),
            Text(
              '$score / $maxScore',
              style: const TextStyle(
                fontWeight: FontWeight.bold,
                fontSize: 12,
              ),
            ),
          ],
        ),
        const SizedBox(height: 6),
        ClipRRect(
          borderRadius: BorderRadius.circular(4),
          child: LinearProgressIndicator(
            value: score / maxScore,
            backgroundColor: Colors.grey.shade200,
            valueColor: AlwaysStoppedAnimation<Color>(
              Color(BlockchainService.getTrustColor(trustLevel)),
            ),
            minHeight: 8,
          ),
        ),
      ],
    );
  }
}
