import 'package:flutter/material.dart';
import 'map_screen.dart'; // DisasterNeed modeline erişim için

class StatisticsScreen extends StatelessWidget {
  const StatisticsScreen({super.key});

  @override
  Widget build(BuildContext context) {
    // Haritadan gelen listeyi alıyoruz
    final List<DisasterNeed> needs = ModalRoute.of(context)!.settings.arguments as List<DisasterNeed>? ?? [];

    // Kategorileri sayalım
    int gidaCount = needs.where((n) => n.category == "Gıda").length;
    int barinakCount = needs.where((n) => n.category == "Barınak").length;
    int tibbiCount = needs.where((n) => n.category == "Tıbbi").length;
    int total = needs.length;

    return Scaffold(
      appBar: AppBar(title: const Text("Muğla Anlık Analiz")),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(20),
        child: Column(
          children: [
            const Text("Haritadaki Gerçek Veriler", style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold)),
            const SizedBox(height: 30),
            
            _buildStatBar("Gıda Yardımı", total > 0 ? gidaCount / total : 0, Colors.orange, "$gidaCount Talep"),
            _buildStatBar("Barınak Desteği", total > 0 ? barinakCount / total : 0, Colors.blue, "$barinakCount Talep"),
            _buildStatBar("Tıbbi Destek", total > 0 ? tibbiCount / total : 0, Colors.red, "$tibbiCount Talep"),

            const SizedBox(height: 40),
            Container(
              padding: const EdgeInsets.all(20),
              decoration: BoxDecoration(color: const Color(0xFF1a2a6c), borderRadius: BorderRadius.circular(20)),
              child: Column(
                children: [
                  _buildRow("Toplam Bildirim", "$total"),
                  _buildRow("Aktif Düğümler", "12"),
                  _buildRow("Ağ Güvenliği", "Yüksek"),
                ],
              ),
            )
          ],
        ),
      ),
    );
  }

  Widget _buildStatBar(String label, double percent, Color color, String count) {
    return Column(
      children: [
        Row(mainAxisAlignment: MainAxisAlignment.spaceBetween, children: [Text(label), Text(count, style: TextStyle(color: color, fontWeight: FontWeight.bold))]),
        const SizedBox(height: 8),
        LinearProgressIndicator(value: percent, minHeight: 12, borderRadius: BorderRadius.circular(10), color: color, backgroundColor: color.withOpacity(0.1)),
        const SizedBox(height: 20),
      ],
    );
  }

  Widget _buildRow(String label, String val) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 8),
      child: Row(mainAxisAlignment: MainAxisAlignment.spaceBetween, children: [Text(label, style: const TextStyle(color: Colors.white70)), Text(val, style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold))]),
    );
  }
}