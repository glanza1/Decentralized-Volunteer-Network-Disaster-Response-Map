import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:flutter_map_marker_cluster/flutter_map_marker_cluster.dart';
import 'package:latlong2/latlong.dart';
import 'package:shared_preferences/shared_preferences.dart';

class DisasterNeed {
  final LatLng location;
  final String description;
  final String category;
  int verificationCount;
  String status;

  DisasterNeed({
    required this.location,
    required this.description,
    required this.category,
    this.verificationCount = 0,
    this.status = 'Açık',
  });

  Map<String, dynamic> toJson() => {
    'lat': location.latitude,
    'lng': location.longitude,
    'desc': description,
    'cat': category,
    'count': verificationCount,
    'status': status,
  };

  factory DisasterNeed.fromJson(Map<String, dynamic> json) {
    return DisasterNeed(
      location: LatLng(json['lat'], json['lng']),
      description: json['desc'],
      category: json['cat'] ?? "Gıda",
      verificationCount: json['count'],
      status: json['status'] ?? 'Açık',
    );
  }
}

class MapScreen extends StatefulWidget {
  const MapScreen({super.key});

  @override
  State<MapScreen> createState() => _MapScreenState();
}

class _MapScreenState extends State<MapScreen> {
  List<DisasterNeed> _needsList = [];
  LatLng? _tappedLocation;
  String _tempCategory = "Gıda";

  @override
  void initState() {
    super.initState();
    _loadData();
  }

  Future<void> _loadData() async {
    final prefs = await SharedPreferences.getInstance();
    final String? needsJson = prefs.getString('saved_needs');
    if (needsJson != null) {
      final List<dynamic> decodedList = jsonDecode(needsJson);
      setState(() {
        _needsList = decodedList.map((item) => DisasterNeed.fromJson(item)).toList();
      });
    }
  }

  Future<void> _saveData() async {
    final prefs = await SharedPreferences.getInstance();
    final String encodedData = jsonEncode(_needsList.map((n) => n.toJson()).toList());
    await prefs.setString('saved_needs', encodedData);
  }

  // --- KULLANICI PUANLARINI ARTIRAN FONKSİYONLAR ---

  Future<void> _recordUserAction(String actionTitle) async {
    final prefs = await SharedPreferences.getInstance();
    List<String> history = prefs.getStringList('user_history') ?? [];
    
    // Yeni aksiyonu en başa ekle
    String timestamp = "${DateTime.now().hour}:${DateTime.now().minute}";
    history.insert(0, "[$timestamp] $actionTitle");
    
    // Toplam teyit/yardım sayılarını artır
    if (actionTitle.contains("Teyit")) {
      int count = prefs.getInt('user_verifications') ?? 0;
      await prefs.setInt('user_verifications', count + 1);
    } else if (actionTitle.contains("Yardım")) {
      int count = prefs.getInt('user_helps') ?? 0;
      await prefs.setInt('user_helps', count + 1);
    }

    await prefs.setStringList('user_history', history);
  }

  void _verifyNeed(int index) {
    setState(() {
      _needsList[index].verificationCount++;
    });
    _saveData();
    _recordUserAction("${_needsList[index].category} talebini teyit ettiniz.");
  }

  void _updateStatus(int index, String newStatus) {
    setState(() {
      _needsList[index].status = newStatus;
    });
    _saveData();
    if (newStatus == 'Yardım Gidiyor') {
      _recordUserAction("${_needsList[index].category} yardımına başladınız.");
    }
  }

  void _addNewNeed(LatLng point, String desc, String cat) {
    setState(() {
      _needsList.add(DisasterNeed(location: point, description: desc, category: cat));
      _tappedLocation = null;
    });
    _saveData();
    _recordUserAction("Yeni bir $cat bildirimi yayınladınız.");
  }

  @override
  Widget build(BuildContext context) {
    final activeNeeds = _needsList.where((n) => n.status != 'Tamamlandı').toList();
    return Scaffold(
      extendBodyBehindAppBar: true,
      body: Stack(
        children: [
          FlutterMap(
            options: MapOptions(
              initialCenter: const LatLng(37.2150, 28.3636),
              initialZoom: 14.0,
              onTap: (tapPos, point) => setState(() => _tappedLocation = point),
            ),
            children: [
              TileLayer(urlTemplate: 'https://tile.openstreetmap.org/{z}/{x}/{y}.png'),
              MarkerClusterLayerWidget(
                options: MarkerClusterLayerOptions(
                  maxClusterRadius: 50,
                  size: const Size(45, 45),
                  markers: activeNeeds.map((need) => _buildMarker(need)).toList(),
                  builder: (context, markers) => Container(
                    decoration: BoxDecoration(shape: BoxShape.circle, color: const Color(0xFF1a2a6c), border: Border.all(color: Colors.white, width: 2)),
                    child: Center(child: Text(markers.length.toString(), style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold))),
                  ),
                ),
              ),
              if (_tappedLocation != null)
                MarkerLayer(markers: [Marker(point: _tappedLocation!, width: 60, height: 60, child: const Icon(Icons.location_searching_rounded, color: Colors.blueAccent, size: 40))]),
            ],
          ),
          _buildFloatingStatusBar(),
          _buildActionButton(),
        ],
      ),
    );
  }

  Marker _buildMarker(DisasterNeed need) {
    int realIndex = _needsList.indexOf(need);
    Color color = need.status == 'Yardım Gidiyor' ? Colors.green : (need.category == "Gıda" ? Colors.orange : (need.category == "Barınak" ? Colors.blue : Colors.red));
    IconData icon = need.category == "Gıda" ? Icons.fastfood_rounded : (need.category == "Barınak" ? Icons.home_rounded : Icons.medical_services_rounded);
    return Marker(
      point: need.location,
      width: 55, height: 55,
      child: GestureDetector(
        onTap: () => _showDetailSheet(need, realIndex),
        child: Container(
          decoration: BoxDecoration(color: Colors.white, shape: BoxShape.circle, border: Border.all(color: color, width: 3), boxShadow: const [BoxShadow(color: Colors.black12, blurRadius: 8)]),
          child: Stack(alignment: Alignment.center, children: [Icon(icon, color: color, size: 28), if (need.status == 'Yardım Gidiyor') const Positioned(top: -2, right: -2, child: Icon(Icons.check_circle, color: Colors.green, size: 18))]),
        ),
      ),
    );
  }

  void _showDetailSheet(DisasterNeed need, int index) {
    showModalBottomSheet(
      context: context,
      backgroundColor: Colors.transparent,
      builder: (context) => Container(
        decoration: const BoxDecoration(color: Colors.white, borderRadius: BorderRadius.vertical(top: Radius.circular(35))),
        padding: const EdgeInsets.all(28),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Row(mainAxisAlignment: MainAxisAlignment.spaceBetween, children: [Text("${need.category}: ${need.description}", style: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold)), Text("${need.verificationCount} Teyit", style: const TextStyle(color: Colors.blue, fontWeight: FontWeight.bold))]),
            const SizedBox(height: 25),
            if (need.status == 'Açık')
              Row(children: [
                Expanded(child: ElevatedButton(onPressed: () { Navigator.pop(context); _verifyNeed(index); }, style: ElevatedButton.styleFrom(backgroundColor: Colors.blueGrey), child: const Text("TEYİT ET", style: TextStyle(color: Colors.white)))),
                const SizedBox(width: 10),
                Expanded(child: ElevatedButton(onPressed: () { Navigator.pop(context); _updateStatus(index, 'Yardım Gidiyor'); }, style: ElevatedButton.styleFrom(backgroundColor: Colors.green), child: const Text("YARDIM ET", style: TextStyle(color: Colors.white)))),
              ]),
            if (need.status == 'Yardım Gidiyor')
              ElevatedButton(onPressed: () { Navigator.pop(context); _updateStatus(index, 'Tamamlandı'); }, style: ElevatedButton.styleFrom(backgroundColor: const Color(0xFF1a2a6c), minimumSize: const Size(double.infinity, 55)), child: const Text("YARDIMI TAMAMLA", style: TextStyle(color: Colors.white))),
          ],
        ),
      ),
    );
  }

  void _showEmergencyDialog(BuildContext context) {
    if (_tappedLocation == null) return;
    final controller = TextEditingController();
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (context) => StatefulBuilder(
        builder: (context, setDialogState) => Container(
          decoration: const BoxDecoration(color: Colors.white, borderRadius: BorderRadius.vertical(top: Radius.circular(35))),
          padding: EdgeInsets.only(bottom: MediaQuery.of(context).viewInsets.bottom + 25, left: 24, right: 24, top: 24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Row(mainAxisAlignment: MainAxisAlignment.spaceBetween, children: [_buildCategoryCard(setDialogState, "Gıda", Icons.fastfood_rounded, Colors.orange), _buildCategoryCard(setDialogState, "Barınak", Icons.home_rounded, Colors.blue), _buildCategoryCard(setDialogState, "Tıbbi", Icons.medical_services_rounded, Colors.red)]),
              const SizedBox(height: 25),
              TextField(controller: controller, decoration: const InputDecoration(labelText: "Açıklama", border: OutlineInputBorder())),
              const SizedBox(height: 25),
              ElevatedButton(onPressed: () { _addNewNeed(_tappedLocation!, controller.text, _tempCategory); Navigator.pop(context); }, style: ElevatedButton.styleFrom(backgroundColor: const Color(0xFF1a2a6c), minimumSize: const Size(double.infinity, 55)), child: const Text("YAYINLA", style: TextStyle(color: Colors.white))),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildCategoryCard(StateSetter setDialogState, String title, IconData icon, Color color) {
    bool isSelected = _tempCategory == title;
    return GestureDetector(onTap: () => setDialogState(() => _tempCategory = title), child: Container(width: 95, padding: const EdgeInsets.symmetric(vertical: 18), decoration: BoxDecoration(color: isSelected ? color.withOpacity(0.12) : Colors.grey[50], borderRadius: BorderRadius.circular(22), border: Border.all(color: isSelected ? color : Colors.transparent, width: 2)), child: Column(children: [Icon(icon, color: isSelected ? color : Colors.blueGrey, size: 30), Text(title)])));
  }

  Widget _buildFloatingStatusBar() {
    return SafeArea(
      child: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Container(
          height: 65,
          decoration: BoxDecoration(color: Colors.white.withOpacity(0.98), borderRadius: BorderRadius.circular(25), boxShadow: const [BoxShadow(color: Colors.black12, blurRadius: 15)]),
          child: Row(
            children: [
              IconButton(icon: const Icon(Icons.account_circle_rounded, color: Color(0xFF1a2a6c), size: 32), onPressed: () => Navigator.pushNamed(context, '/profile')),
              IconButton(icon: const Icon(Icons.analytics_rounded, color: Color(0xFF1a2a6c), size: 30), onPressed: () => Navigator.pushNamed(context, '/statistics', arguments: _needsList)),
              IconButton(icon: const Icon(Icons.list_alt_rounded, color: Color(0xFF1a2a6c), size: 30), onPressed: () => Navigator.pushNamed(context, '/list', arguments: _needsList)),
              const Expanded(child: Center(child: Text("Muğla Dağıtık Ağı", style: TextStyle(fontWeight: FontWeight.bold, color: Color(0xFF1a2a6c))))),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildActionButton() {
    return Positioned(bottom: 35, left: 25, right: 25, child: FloatingActionButton.extended(onPressed: () => _showEmergencyDialog(context), backgroundColor: const Color(0xFFb21f1f), label: const Text("İHTİYAÇ BİLDİR", style: TextStyle(color: Colors.white, fontWeight: FontWeight.bold)), icon: const Icon(Icons.broadcast_on_home_rounded, color: Colors.white)));
  }
}