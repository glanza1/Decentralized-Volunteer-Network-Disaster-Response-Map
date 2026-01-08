import 'dart:convert';
import 'package:http/http.dart' as http;
import 'api_service.dart';

/// Blockchain Service for interacting with smart contracts via backend API
/// 
/// Provides methods to:
/// - Get volunteer identity and trust levels
/// - Check MESH token rewards
/// - Register/verify tasks on blockchain
class BlockchainService {
  static final BlockchainService _instance = BlockchainService._internal();
  factory BlockchainService() => _instance;
  BlockchainService._internal();

  // Use same config as ApiService
  String get baseUrl => '${ApiService.baseUrl}/blockchain';
  
  Map<String, String> get _headers => {
    'Content-Type': 'application/json',
    'X-API-Key': ApiService.apiKey,
  };

  // ============================================================
  // IDENTITY & TRUST
  // ============================================================

  /// Get trust level for a wallet address
  /// Returns: { address, trustLevel (0-4), trustLevelName }
  Future<Map<String, dynamic>?> getTrustLevel(String address) async {
    try {
      final response = await http.get(
        Uri.parse('$baseUrl/trust-level/$address'),
        headers: _headers,
      ).timeout(const Duration(seconds: 10));
      
      if (response.statusCode == 200) {
        return json.decode(response.body);
      }
      return null;
    } catch (e) {
      print('Blockchain API Error: $e');
      return null;
    }
  }

  /// Get full identity info for a wallet address
  /// Returns: { tokenId, reputationScore, tasksCompleted, trustLevel, ... }
  Future<Map<String, dynamic>?> getIdentity(String address) async {
    try {
      final response = await http.get(
        Uri.parse('$baseUrl/identity/$address'),
        headers: _headers,
      ).timeout(const Duration(seconds: 10));
      
      if (response.statusCode == 200) {
        return json.decode(response.body);
      }
      return null;
    } catch (e) {
      print('Blockchain API Error: $e');
      return null;
    }
  }

  /// Register as a volunteer on blockchain
  /// Returns: { success, transactionHash, message }
  Future<Map<String, dynamic>?> registerVolunteer(String metadataUri) async {
    try {
      final response = await http.post(
        Uri.parse('$baseUrl/register'),
        headers: _headers,
        body: json.encode({'metadata_uri': metadataUri}),
      ).timeout(const Duration(seconds: 30));
      
      if (response.statusCode == 200) {
        return json.decode(response.body);
      }
      return null;
    } catch (e) {
      print('Blockchain API Error: $e');
      return null;
    }
  }

  // ============================================================
  // MESH TOKEN REWARDS
  // ============================================================

  /// Get MESH token stats for a node/wallet
  /// Returns: { packetsRelayed, uptimeMinutes, balance, totalEarned }
  Future<Map<String, dynamic>?> getMeshStats(String address) async {
    try {
      final response = await http.get(
        Uri.parse('$baseUrl/mesh/$address/stats'),
        headers: _headers,
      ).timeout(const Duration(seconds: 10));
      
      if (response.statusCode == 200) {
        return json.decode(response.body);
      }
      return null;
    } catch (e) {
      print('Blockchain API Error: $e');
      return null;
    }
  }

  /// Get MESH token balance
  Future<double?> getMeshBalance(String address) async {
    try {
      final response = await http.get(
        Uri.parse('$baseUrl/mesh/$address/balance'),
        headers: _headers,
      ).timeout(const Duration(seconds: 10));
      
      if (response.statusCode == 200) {
        final data = json.decode(response.body);
        return (data['balance'] as num?)?.toDouble();
      }
      return null;
    } catch (e) {
      print('Blockchain API Error: $e');
      return null;
    }
  }

  // ============================================================
  // TASK OPERATIONS
  // ============================================================

  /// Get task verification status from blockchain
  Future<Map<String, dynamic>?> getTaskStatus(String taskId) async {
    try {
      final response = await http.get(
        Uri.parse('$baseUrl/task/$taskId/status'),
        headers: _headers,
      ).timeout(const Duration(seconds: 10));
      
      if (response.statusCode == 200) {
        return json.decode(response.body);
      }
      return null;
    } catch (e) {
      print('Blockchain API Error: $e');
      return null;
    }
  }

  /// Verify a task on blockchain (requires trust level 2+)
  Future<Map<String, dynamic>?> verifyTask(String taskId) async {
    try {
      final response = await http.post(
        Uri.parse('$baseUrl/task/$taskId/verify'),
        headers: _headers,
      ).timeout(const Duration(seconds: 30));
      
      if (response.statusCode == 200) {
        return json.decode(response.body);
      }
      return null;
    } catch (e) {
      print('Blockchain API Error: $e');
      return null;
    }
  }

  // ============================================================
  // DONATIONS
  // ============================================================

  /// Get donation pool status for a task
  Future<Map<String, dynamic>?> getDonationStatus(String taskId) async {
    try {
      final response = await http.get(
        Uri.parse('$baseUrl/donation/$taskId/status'),
        headers: _headers,
      ).timeout(const Duration(seconds: 10));
      
      if (response.statusCode == 200) {
        return json.decode(response.body);
      }
      return null;
    } catch (e) {
      print('Blockchain API Error: $e');
      return null;
    }
  }

  // ============================================================
  // HELPER METHODS
  // ============================================================

  /// Get trust level badge color
  static int getTrustColor(int trustLevel) {
    switch (trustLevel) {
      case 4: return 0xFF4CAF50; // Highly Trusted - Green
      case 3: return 0xFF8BC34A; // Trusted - Light Green
      case 2: return 0xFFFFC107; // Neutral - Yellow
      case 1: return 0xFFFF9800; // Low Trust - Orange
      default: return 0xFF9E9E9E; // Untrusted - Gray
    }
  }

  /// Get trust level name
  static String getTrustName(int trustLevel) {
    switch (trustLevel) {
      case 4: return 'Highly Trusted';
      case 3: return 'Trusted';
      case 2: return 'Neutral';
      case 1: return 'Low Trust';
      default: return 'New User';
    }
  }

  /// Get trust level icon
  static String getTrustIcon(int trustLevel) {
    switch (trustLevel) {
      case 4: return '⭐⭐⭐⭐';
      case 3: return '⭐⭐⭐';
      case 2: return '⭐⭐';
      case 1: return '⭐';
      default: return '○';
    }
  }
}
