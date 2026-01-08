import 'package:flutter/material.dart';
import 'map_screen.dart'; // DisasterNeed modeline erişim için
import '../services/blockchain_service.dart';
import '../services/api_service.dart';

class ListScreen extends StatefulWidget {
  const ListScreen({super.key});

  @override
  State<ListScreen> createState() => _ListScreenState();
}

class _ListScreenState extends State<ListScreen> {
  String _selectedFilter = "Hepsi";
  final BlockchainService _blockchain = BlockchainService();
  final ApiService _api = ApiService();
  bool _isLoading = false;

  @override
  Widget build(BuildContext context) {
    final List<DisasterNeed> allNeeds = ModalRoute.of(context)!.settings.arguments as List<DisasterNeed>? ?? [];

    final List<DisasterNeed> filteredNeeds = _selectedFilter == "Hepsi"
        ? allNeeds
        : allNeeds.where((need) => need.category == _selectedFilter).toList();

    return Scaffold(
      appBar: AppBar(
        title: const Text("İhtiyaçları Filtrele"),
        centerTitle: true,
      ),
      body: Column(
        children: [
          // --- FILTER CHIPS ---
          Padding(
            padding: const EdgeInsets.symmetric(vertical: 12.0),
            child: SingleChildScrollView(
              scrollDirection: Axis.horizontal,
              padding: const EdgeInsets.symmetric(horizontal: 16),
              child: Row(
                children: [
                  _buildFilterChip("Hepsi", Icons.all_inclusive, Colors.blueGrey),
                  _buildFilterChip("Gıda", Icons.fastfood, Colors.orange),
                  _buildFilterChip("Barınak", Icons.home, Colors.blue),
                  _buildFilterChip("Tıbbi", Icons.medical_services, Colors.red),
                ],
              ),
            ),
          ),

          // --- FILTERED LIST ---
          Expanded(
            child: filteredNeeds.isEmpty
                ? Center(
                    child: Column(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        Icon(Icons.search_off, size: 60, color: Colors.grey[300]),
                        const SizedBox(height: 10),
                        Text("Bu kategoride ilan bulunamadı.", style: TextStyle(color: Colors.grey[600])),
                      ],
                    ),
                  )
                : ListView.builder(
                    padding: const EdgeInsets.all(16),
                    itemCount: filteredNeeds.length,
                    itemBuilder: (context, index) {
                      final need = filteredNeeds[index];
                      return _buildNeedCard(need);
                    },
                  ),
          ),
        ],
      ),
    );
  }

  Widget _buildFilterChip(String label, IconData icon, Color color) {
    bool isSelected = _selectedFilter == label;
    return Padding(
      padding: const EdgeInsets.only(right: 8.0),
      child: FilterChip(
        avatar: Icon(icon, size: 16, color: isSelected ? Colors.white : color),
        label: Text(label),
        selected: isSelected,
        onSelected: (bool selected) {
          setState(() {
            _selectedFilter = label;
          });
        },
        selectedColor: color,
        checkmarkColor: Colors.white,
        labelStyle: TextStyle(
          color: isSelected ? Colors.white : Colors.black87,
          fontWeight: isSelected ? FontWeight.bold : FontWeight.normal,
        ),
        backgroundColor: color.withOpacity(0.05),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      ),
    );
  }

  Widget _buildNeedCard(DisasterNeed need) {
    Color categoryColor = need.category == "Gıda" ? Colors.orange : (need.category == "Barınak" ? Colors.blue : Colors.red);
    
    return Card(
      margin: const EdgeInsets.only(bottom: 16),
      elevation: 3,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Text(
                  need.category,
                  style: TextStyle(color: categoryColor, fontWeight: FontWeight.bold, fontSize: 14),
                ),
                Row(
                  children: [
                    const Icon(Icons.verified_user, size: 14, color: Colors.green),
                    const SizedBox(width: 4),
                    Text("${need.verificationCount} Teyit", style: const TextStyle(fontSize: 12, color: Colors.green, fontWeight: FontWeight.bold)),
                  ],
                ),
              ],
            ),
            const SizedBox(height: 12),
            Text(need.description, style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w500)),
            const SizedBox(height: 12),
            
            // ═══════════════════════════════════════════════════════
            // 🔗 BLOCKCHAIN ACTION BUTTONS
            // ═══════════════════════════════════════════════════════
            Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: Colors.blue.shade50,
                borderRadius: BorderRadius.circular(12),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Icon(Icons.link, size: 14, color: Colors.blue.shade700),
                      const SizedBox(width: 4),
                      Text(
                        "Blockchain Actions",
                        style: TextStyle(
                          fontSize: 12,
                          fontWeight: FontWeight.bold,
                          color: Colors.blue.shade700,
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 8),
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceEvenly,
                    children: [
                      _buildActionButton(
                        "Verify",
                        Icons.verified,
                        Colors.green,
                        () => _onVerify(need),
                        "+5 pts",
                      ),
                      _buildActionButton(
                        "Accept",
                        Icons.handshake,
                        Colors.blue,
                        () => _onAccept(need),
                        "Volunteer",
                      ),
                      _buildActionButton(
                        "Complete",
                        Icons.check_circle,
                        Colors.purple,
                        () => _onComplete(need),
                        "+50 pts",
                      ),
                    ],
                  ),
                ],
              ),
            ),
            
            const SizedBox(height: 12),
            const Divider(),
            Align(
              alignment: Alignment.centerRight,
              child: TextButton.icon(
                onPressed: () => Navigator.pop(context),
                icon: const Icon(Icons.map_outlined, size: 16),
                label: const Text("Konumu Gör"),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildActionButton(String label, IconData icon, Color color, VoidCallback onPressed, String subtitle) {
    return Column(
      children: [
        ElevatedButton(
          onPressed: _isLoading ? null : onPressed,
          style: ElevatedButton.styleFrom(
            backgroundColor: color,
            foregroundColor: Colors.white,
            shape: const CircleBorder(),
            padding: const EdgeInsets.all(12),
          ),
          child: Icon(icon, size: 20),
        ),
        const SizedBox(height: 4),
        Text(label, style: TextStyle(fontSize: 10, fontWeight: FontWeight.bold, color: color)),
        Text(subtitle, style: TextStyle(fontSize: 9, color: Colors.grey.shade600)),
      ],
    );
  }

  // 🔗 Blockchain Actions
  Future<void> _onVerify(DisasterNeed need) async {
    setState(() => _isLoading = true);
    try {
      // Note: In production, use actual request ID from backend
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Row(
            children: const [
              Icon(Icons.verified, color: Colors.white),
              SizedBox(width: 8),
              Expanded(child: Text("✅ Verified! You earned +5 reputation points!")),
            ],
          ),
          backgroundColor: Colors.green,
          duration: const Duration(seconds: 3),
        ),
      );
      
      // Increment local verification count
      setState(() {
        need.verificationCount++;
      });
    } catch (e) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text("Error: $e"), backgroundColor: Colors.red),
      );
    } finally {
      setState(() => _isLoading = false);
    }
  }

  Future<void> _onAccept(DisasterNeed need) async {
    setState(() => _isLoading = true);
    try {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Row(
            children: const [
              Icon(Icons.handshake, color: Colors.white),
              SizedBox(width: 8),
              Expanded(child: Text("🤝 Accepted! Complete the task to earn +50 points!")),
            ],
          ),
          backgroundColor: Colors.blue,
          duration: const Duration(seconds: 3),
        ),
      );
    } catch (e) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text("Error: $e"), backgroundColor: Colors.red),
      );
    } finally {
      setState(() => _isLoading = false);
    }
  }

  Future<void> _onComplete(DisasterNeed need) async {
    setState(() => _isLoading = true);
    try {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Row(
            children: const [
              Icon(Icons.celebration, color: Colors.white),
              SizedBox(width: 8),
              Expanded(child: Text("🎉 Completed! Volunteer earned +50 reputation points!")),
            ],
          ),
          backgroundColor: Colors.purple,
          duration: const Duration(seconds: 3),
        ),
      );
    } catch (e) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text("Error: $e"), backgroundColor: Colors.red),
      );
    } finally {
      setState(() => _isLoading = false);
    }
  }
}