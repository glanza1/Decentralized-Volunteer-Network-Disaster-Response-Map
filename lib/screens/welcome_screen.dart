import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';

class WelcomeScreen extends StatefulWidget {
  const WelcomeScreen({super.key});

  @override
  State<WelcomeScreen> createState() => _WelcomeScreenState();
}

class _WelcomeScreenState extends State<WelcomeScreen> {
  final TextEditingController _nameController = TextEditingController();

  bool _isValidEthereumAddress(String address) {
    final regex = RegExp(r'^0x[a-fA-F0-9]{40}$');
    return regex.hasMatch(address);
  }

  Future<void> _saveNameAndEnter() async {
    final input = _nameController.text.trim();
    
    if (input.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text("Lütfen cüzdan adresinizi girin!")),
      );
      return;
    }
    
    if (!_isValidEthereumAddress(input)) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text("Geçersiz cüzdan adresi! 0x ile başlayan 42 karakterlik adres girin."),
          backgroundColor: Colors.red,
        ),
      );
      return;
    }
    
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString('user_nickname', input);
    if (mounted) Navigator.pushNamed(context, '/map');
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Container(
        width: double.infinity,
        decoration: const BoxDecoration(
          gradient: LinearGradient(
            colors: [Color(0xFF1a2a6c), Color(0xFFb21f1f), Color(0xFFfdbb2d)],
          ),
        ),
        child: Center(
          child: SingleChildScrollView(
            child: Card(
              margin: const EdgeInsets.all(24),
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(25)),
              child: Padding(
                padding: const EdgeInsets.all(32),
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    const Icon(Icons.hub_rounded, size: 60, color: Colors.redAccent),
                    const SizedBox(height: 20),
                    const Text('Muğla P2P Ağı', style: TextStyle(fontSize: 24, fontWeight: FontWeight.bold)),
                    const SizedBox(height: 30),
                    TextField(
                      controller: _nameController,
                      decoration: InputDecoration(
                        labelText: 'Cüzdan Adresi (0x...)',
                        border: OutlineInputBorder(borderRadius: BorderRadius.circular(15)),
                      ),
                    ),
                    const SizedBox(height: 20),
                    ElevatedButton(
                      onPressed: _saveNameAndEnter,
                      style: ElevatedButton.styleFrom(
                        backgroundColor: const Color(0xFF1a2a6c),
                        minimumSize: const Size(double.infinity, 50),
                      ),
                      child: const Text('AĞA BAĞLAN', style: TextStyle(color: Colors.white)),
                    ),
                  ],
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}