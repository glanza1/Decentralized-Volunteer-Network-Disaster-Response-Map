import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';

class ProfileScreen extends StatefulWidget {
  const ProfileScreen({super.key});

  @override
  State<ProfileScreen> createState() => _ProfileScreenState(); // İsmi kontrol et
}

// DÜZELTİLEN KISIM: Sınıf ismi _ProfileScreenState olarak güncellendi
class _ProfileScreenState extends State<ProfileScreen> {
  String _nickname = "Yükleniyor...";
  int _verifications = 0;
  int _helps = 0;
  List<String> _history = [];
  double _trustScore = 5.0; // Başlangıç skoru

  @override
  void initState() {
    super.initState();
    _loadProfileData();
  }

  // Kalıcı hafızadan verileri çeken fonksiyon
  Future<void> _loadProfileData() async {
    final prefs = await SharedPreferences.getInstance(); //
    setState(() {
      _nickname = prefs.getString('user_nickname') ?? "Gezgin";
      _verifications = prefs.getInt('user_verifications') ?? 0;
      _helps = prefs.getInt('user_helps') ?? 0;
      _history = prefs.getStringList('user_history') ?? [];
      
      // MÜHENDİSLİK ALGORİTMASI: Teyit +0.2, Yardım +0.5 puan.
      _trustScore = (5.0 + (_verifications * 0.2) + (_helps * 0.5)).clamp(0.0, 10.0);
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text("P2P Dijital Kimliğim"), centerTitle: true),
      body: Column(
        children: [
          const SizedBox(height: 30),
          const CircleAvatar(
            radius: 50, 
            backgroundColor: Color(0xFF1a2a6c), 
            child: Icon(Icons.person, size: 50, color: Colors.white)
          ),
          const SizedBox(height: 15),
          Text(_nickname, style: const TextStyle(fontSize: 24, fontWeight: FontWeight.bold)),
          const Text("Düğüm ID: 0x71C...92bD", style: TextStyle(fontFamily: 'monospace', color: Colors.grey)),
          const SizedBox(height: 30),
          
          // GÜVEN SKORU KARTI
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 20),
            child: Card(
              elevation: 8,
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
              color: Colors.blue.shade50,
              child: ListTile(
                leading: const Icon(Icons.verified_user, color: Colors.green, size: 40),
                title: Text(
                  "Güven Skoru: ${_trustScore.toStringAsFixed(1)} / 10", 
                  style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 18)
                ),
                subtitle: const Text("Topluluk onaylı güvenilir düğüm."),
              ),
            ),
          ),
          
          const SizedBox(height: 25),
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceEvenly,
            children: [
              _buildSmallStat("Teyitler", _verifications.toString(), Colors.blue),
              _buildSmallStat("Yardımlar", _helps.toString(), Colors.green),
            ],
          ),

          const Divider(height: 40, indent: 20, endIndent: 20),
          const Padding(
            padding: EdgeInsets.symmetric(horizontal: 20),
            child: Align(
              alignment: Alignment.centerLeft, 
              child: Text("Aktivite Geçmişi", style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold))
            ),
          ),
          
          Expanded(
            child: _history.isEmpty 
              ? const Center(child: Text("Henüz bir aktivite yok."))
              : ListView.builder(
                  padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 10),
                  itemCount: _history.length,
                  itemBuilder: (context, index) => Card(
                    margin: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
                    child: ListTile(
                      leading: const Icon(Icons.history_toggle_off, color: Colors.blueGrey),
                      title: Text(_history[index], style: const TextStyle(fontSize: 14)),
                    ),
                  ),
                ),
          ),
        ],
      ),
    );
  }

  Widget _buildSmallStat(String label, String value, Color color) {
    return Column(
      children: [
        Text(value, style: TextStyle(fontSize: 22, fontWeight: FontWeight.bold, color: color)),
        Text(label, style: const TextStyle(color: Colors.grey, fontWeight: FontWeight.w500)),
      ],
    );
  }
}