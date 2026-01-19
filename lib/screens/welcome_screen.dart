import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../services/api_service.dart';

class WelcomeScreen extends StatefulWidget {
  const WelcomeScreen({super.key});

  @override
  State<WelcomeScreen> createState() => _WelcomeScreenState();
}

class _WelcomeScreenState extends State<WelcomeScreen> {
  final TextEditingController _nameController = TextEditingController();
  bool _isLoading = false;

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

    // Check if wallet exists in the system
    setState(() => _isLoading = true);
    
    try {
      final walletExists = await ApiService().checkWalletExists(input);
      
      if (!walletExists) {
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(
              content: Text("Bu cüzdan adresi sistemde kayıtlı değil!"),
              backgroundColor: Colors.orange,
            ),
          );
        }
        setState(() => _isLoading = false);
        return;
      }
      
      final prefs = await SharedPreferences.getInstance();
      await prefs.setString('user_nickname', input);
      if (mounted) Navigator.pushNamed(context, '/map');
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text("Bağlantı hatası: $e"),
            backgroundColor: Colors.red,
          ),
        );
      }
    } finally {
      if (mounted) setState(() => _isLoading = false);
    }
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
                        hintText: '0xF018C3A8cfa5B17a36180a293092Ec884B8ecA61',
                      ),
                    ),
                    const SizedBox(height: 20),
                    ElevatedButton(
                      onPressed: _isLoading ? null : _saveNameAndEnter,
                      style: ElevatedButton.styleFrom(
                        backgroundColor: const Color(0xFF1a2a6c),
                        minimumSize: const Size(double.infinity, 50),
                      ),
                      child: _isLoading 
                        ? const SizedBox(
                            width: 20, 
                            height: 20, 
                            child: CircularProgressIndicator(color: Colors.white, strokeWidth: 2)
                          )
                        : const Text('AĞA BAĞLAN', style: TextStyle(color: Colors.white)),
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