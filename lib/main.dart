import 'package:flutter/material.dart';
import 'screens/welcome_screen.dart';
import 'screens/map_screen.dart';
import 'screens/profile_screen.dart';
import 'screens/statistics_screen.dart';
import 'screens/list_screen.dart'; // Yeni import

void main() => runApp(const DisasterNetworkApp());

class DisasterNetworkApp extends StatelessWidget {
  const DisasterNetworkApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      debugShowCheckedModeBanner: false,
      title: 'Muğla P2P Afet Ağı',
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(seedColor: const Color(0xFF1a2a6c)),
        useMaterial3: true,
      ),
      initialRoute: '/',
      routes: {
        '/': (context) => const WelcomeScreen(),
        '/map': (context) => const MapScreen(),
        '/profile': (context) => const ProfileScreen(),
        '/statistics': (context) => const StatisticsScreen(),
        '/list': (context) => const ListScreen(), // Yeni rota
      },
    );
  }
}