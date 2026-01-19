import 'dart:convert';
import 'dart:io';
import 'package:http/http.dart' as http;

/// API Service for communicating with the Python backend
/// 
/// SECURITY FEATURES:
/// - HTTPS support (accepts self-signed certificates for development)
/// - API key authentication via X-API-Key header
class ApiService {
  // ============================================================
  // CONFIGURATION - MODIFY THESE VALUES
  // ============================================================
  
  // Backend server address (use your computer's IP for mobile)
  static const String backendHost = 'localhost';
  static const int backendPort = 8000;
  
  // 🔐 API Key - Get this from the backend when it first starts
  // The backend prints the API key on first run
  static const String apiKey = '4hEjqhixAz1id6I0qLv8O7DxCiDzxC0Zou59_P0BcvU';
  
  // Use HTTPS (set to false for development with self-signed certs)
  static const bool useHttps = false;
  
  // ============================================================
  
  static String get _protocol => useHttps ? 'https' : 'http';
  static String get baseUrl => '$_protocol://$backendHost:$backendPort/api';
  
  static final ApiService _instance = ApiService._internal();
  factory ApiService() => _instance;
  ApiService._internal();

  // Create HTTP client that accepts self-signed certificates (for development)
  http.Client get _client {
    return http.Client();
  }

  // Common headers with API key
  Map<String, String> get _headers => {
    'Content-Type': 'application/json',
    'X-API-Key': apiKey,
  };

  /// Get all local help requests from the backend
  Future<List<Map<String, dynamic>>> getLocalRequests() async {
    try {
      final response = await http.get(
        Uri.parse('$baseUrl/local-requests'),
        headers: _headers,
      ).timeout(const Duration(seconds: 10));
      
      if (response.statusCode == 200) {
        final List<dynamic> data = json.decode(response.body);
        return data.cast<Map<String, dynamic>>();
      }
      throw Exception('Failed to load requests: ${response.statusCode}');
    } catch (e) {
      print('API Error: $e');
      return [];
    }
  }

  /// Get nearby help requests based on location
  Future<List<Map<String, dynamic>>> getNearbyRequests({
    required double latitude,
    required double longitude,
    double radiusKm = 10.0,
  }) async {
    try {
      final response = await http.get(
        Uri.parse('$baseUrl/nearby-requests?latitude=$latitude&longitude=$longitude&radius_km=$radiusKm'),
        headers: _headers,
      ).timeout(const Duration(seconds: 10));
      
      if (response.statusCode == 200) {
        final List<dynamic> data = json.decode(response.body);
        return data.cast<Map<String, dynamic>>();
      }
      throw Exception('Failed to load nearby requests: ${response.statusCode}');
    } catch (e) {
      print('API Error: $e');
      return [];
    }
  }

  /// Create and broadcast a new help request
  /// 🔐 Requires valid API key
  Future<Map<String, dynamic>?> createHelpRequest({
    required double latitude,
    required double longitude,
    required String requestType,
    required String priority,
    required String title,
    required String description,
    String? contactInfo,
  }) async {
    try {
      final response = await http.post(
        Uri.parse('$baseUrl/help-request'),
        headers: _headers,
        body: json.encode({
          'location': {
            'latitude': latitude,
            'longitude': longitude,
          },
          'request_type': requestType,
          'priority': priority,
          'title': title,
          'description': description,
          if (contactInfo != null) 'contact_info': contactInfo,
        }),
      ).timeout(const Duration(seconds: 10));
      
      if (response.statusCode == 201) {
        return json.decode(response.body);
      }
      
      // Handle auth errors
      if (response.statusCode == 401) {
        print('API Error: API key required. Set your API key in api_service.dart');
      } else if (response.statusCode == 403) {
        print('API Error: Invalid API key');
      } else {
        print('API Error: ${response.statusCode} - ${response.body}');
      }
      
      throw Exception('Failed to create request: ${response.statusCode}');
    } catch (e) {
      print('API Error: $e');
      return null;
    }
  }

  /// Get network statistics
  Future<Map<String, dynamic>?> getNetworkStats() async {
    try {
      final response = await http.get(
        Uri.parse('$baseUrl/network/stats'),
        headers: _headers,
      ).timeout(const Duration(seconds: 10));
      
      if (response.statusCode == 200) {
        return json.decode(response.body);
      }
      throw Exception('Failed to load stats: ${response.statusCode}');
    } catch (e) {
      print('API Error: $e');
      return null;
    }
  }

  /// Get list of connected peers
  Future<List<Map<String, dynamic>>> getPeers() async {
    try {
      final response = await http.get(
        Uri.parse('$baseUrl/network/peers'),
        headers: _headers,
      ).timeout(const Duration(seconds: 10));
      
      if (response.statusCode == 200) {
        final List<dynamic> data = json.decode(response.body);
        return data.cast<Map<String, dynamic>>();
      }
      throw Exception('Failed to load peers: ${response.statusCode}');
    } catch (e) {
      print('API Error: $e');
      return [];
    }
  }

  /// Check if backend is reachable
  Future<bool> isConnected() async {
    try {
      final response = await http.get(
        Uri.parse('$baseUrl/network/stats'),
        headers: _headers,
      ).timeout(const Duration(seconds: 5));
      return response.statusCode == 200;
    } catch (e) {
      return false;
    }
  }

  /// Check if a wallet address exists in the system
  Future<bool> checkWalletExists(String address) async {
    try {
      final response = await http.get(
        Uri.parse('$baseUrl/wallet/list'),
        headers: _headers,
      ).timeout(const Duration(seconds: 5));
      
      if (response.statusCode == 200) {
        final List<dynamic> wallets = json.decode(response.body);
        final normalizedAddress = address.toLowerCase();
        return wallets.any((w) => 
          (w['address'] as String).toLowerCase() == normalizedAddress
        );
      }
      return false;
    } catch (e) {
      print('Wallet check error: $e');
      return false;
    }
  }
}
