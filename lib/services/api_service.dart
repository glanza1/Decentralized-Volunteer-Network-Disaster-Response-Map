import 'dart:convert';
import 'package:http/http.dart' as http;

/// API Service for communicating with the Python backend
class ApiService {
  // Change this to your backend IP if running on a different machine
  static const String baseUrl = 'http://localhost:8000/api';
  
  static final ApiService _instance = ApiService._internal();
  factory ApiService() => _instance;
  ApiService._internal();

  /// Get all local help requests from the backend
  Future<List<Map<String, dynamic>>> getLocalRequests() async {
    try {
      final response = await http.get(
        Uri.parse('$baseUrl/local-requests'),
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
        headers: {'Content-Type': 'application/json'},
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
      ).timeout(const Duration(seconds: 5));
      return response.statusCode == 200;
    } catch (e) {
      return false;
    }
  }
}
