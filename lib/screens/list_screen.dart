import 'package:flutter/material.dart';
import 'map_screen.dart'; // DisasterNeed modeline erişim için

class ListScreen extends StatefulWidget {
  const ListScreen({super.key});

  @override
  State<ListScreen> createState() => _ListScreenState();
}

class _ListScreenState extends State<ListScreen> {
  String _selectedFilter = "Hepsi"; // Varsayılan filtre

  @override
  Widget build(BuildContext context) {
    // Haritadan gelen ana listeyi alıyoruz
    final List<DisasterNeed> allNeeds = ModalRoute.of(context)!.settings.arguments as List<DisasterNeed>? ?? [];

    // Filtreleme mantığı: Seçili kategoriye göre listeyi süzüyoruz
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
          // --- FİLTRELEME BUTONLARI (CHIPS) ---
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

          // --- FİLTRELENMİŞ LİSTE ---
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

  // Modern Filtre Butonu Tasarımı
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

  // Liste Kartı Tasarımı
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
}