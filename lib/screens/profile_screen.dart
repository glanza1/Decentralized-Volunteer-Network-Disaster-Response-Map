import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../services/blockchain_service.dart';

class ProfileScreen extends StatefulWidget {
  const ProfileScreen({super.key});

  @override
  State<ProfileScreen> createState() => _ProfileScreenState();
}

class _ProfileScreenState extends State<ProfileScreen> {
  String _nickname = "Yükleniyor...";
  int _verifications = 0;
  int _helps = 0;
  List<String> _history = [];
  double _trustScore = 5.0;
  
  // 🔗 BLOCKCHAIN DATA
  final BlockchainService _blockchain = BlockchainService();
  bool _blockchainLoading = true;
  int _blockchainTrustLevel = 0;
  int _reputationScore = 0;
  int _tasksCompleted = 0;
  double _meshBalance = 0.0;
  int _packetsRelayed = 0;
  
  // Test wallet address (in production, get from user's wallet)
  static const String _testAddress = "0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266";

  @override
  void initState() {
    super.initState();
    _loadProfileData();
    _loadBlockchainData();
  }

  Future<void> _loadProfileData() async {
    final prefs = await SharedPreferences.getInstance();
    setState(() {
      _nickname = prefs.getString('user_nickname') ?? "Gezgin";
      _verifications = prefs.getInt('user_verifications') ?? 0;
      _helps = prefs.getInt('user_helps') ?? 0;
      _history = prefs.getStringList('user_history') ?? [];
      _trustScore = (5.0 + (_verifications * 0.2) + (_helps * 0.5)).clamp(0.0, 10.0);
    });
  }

  // 🔗 Load data from blockchain
  Future<void> _loadBlockchainData() async {
    try {
      // Get identity info
      final identity = await _blockchain.getIdentity(_testAddress);
      if (identity != null) {
        setState(() {
          _blockchainTrustLevel = identity['trustLevel'] ?? 0;
          _reputationScore = identity['reputationScore'] ?? 0;
          _tasksCompleted = identity['tasksCompleted'] ?? 0;
        });
      }
      
      // Get MESH token stats
      final meshStats = await _blockchain.getMeshStats(_testAddress);
      if (meshStats != null) {
        setState(() {
          _meshBalance = (meshStats['balance'] as num?)?.toDouble() ?? 0.0;
          _packetsRelayed = meshStats['packetsRelayed'] ?? 0;
        });
      }
      
      setState(() {
        _blockchainLoading = false;
      });
    } catch (e) {
      print('Blockchain data load error: $e');
      setState(() {
        _blockchainLoading = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text("P2P Dijital Kimliğim"),
        centerTitle: true,
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            onPressed: () {
              setState(() => _blockchainLoading = true);
              _loadBlockchainData();
            },
          ),
        ],
      ),
      body: SingleChildScrollView(
        child: Column(
          children: [
            const SizedBox(height: 30),
            const CircleAvatar(
              radius: 50,
              backgroundColor: Color(0xFF1a2a6c),
              child: Icon(Icons.person, size: 50, color: Colors.white),
            ),
            const SizedBox(height: 15),
            Text(_nickname, style: const TextStyle(fontSize: 24, fontWeight: FontWeight.bold)),
            Text(
              "Cüzdan: ${_testAddress.substring(0, 8)}...${_testAddress.substring(38)}",
              style: const TextStyle(fontFamily: 'monospace', color: Colors.grey),
            ),
            const SizedBox(height: 20),

            // ═══════════════════════════════════════════════════════════
            // 🔗 BLOCKCHAIN TRUST LEVEL CARD
            // ═══════════════════════════════════════════════════════════
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 20),
              child: Card(
                elevation: 8,
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
                child: Container(
                  decoration: BoxDecoration(
                    borderRadius: BorderRadius.circular(20),
                    gradient: LinearGradient(
                      colors: [
                        Color(BlockchainService.getTrustColor(_blockchainTrustLevel)).withOpacity(0.2),
                        Colors.white,
                      ],
                      begin: Alignment.topLeft,
                      end: Alignment.bottomRight,
                    ),
                  ),
                  child: Padding(
                    padding: const EdgeInsets.all(20),
                    child: Column(
                      children: [
                        Row(
                          mainAxisAlignment: MainAxisAlignment.center,
                          children: [
                            Icon(
                              Icons.verified_user,
                              color: Color(BlockchainService.getTrustColor(_blockchainTrustLevel)),
                              size: 40,
                            ),
                            const SizedBox(width: 10),
                            Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                const Text("🔗 Blockchain Trust Level",
                                    style: TextStyle(fontSize: 12, color: Colors.grey)),
                                _blockchainLoading
                                    ? const SizedBox(
                                        width: 20,
                                        height: 20,
                                        child: CircularProgressIndicator(strokeWidth: 2),
                                      )
                                    : Text(
                                        BlockchainService.getTrustIcon(_blockchainTrustLevel),
                                        style: const TextStyle(fontSize: 24),
                                      ),
                              ],
                            ),
                          ],
                        ),
                        const SizedBox(height: 15),
                        Text(
                          BlockchainService.getTrustName(_blockchainTrustLevel),
                          style: TextStyle(
                            fontSize: 22,
                            fontWeight: FontWeight.bold,
                            color: Color(BlockchainService.getTrustColor(_blockchainTrustLevel)),
                          ),
                        ),
                        const SizedBox(height: 5),
                        Text(
                          "Reputation: $_reputationScore / 1000",
                          style: const TextStyle(color: Colors.grey),
                        ),
                        const SizedBox(height: 10),
                        LinearProgressIndicator(
                          value: _reputationScore / 1000,
                          backgroundColor: Colors.grey.shade200,
                          valueColor: AlwaysStoppedAnimation<Color>(
                            Color(BlockchainService.getTrustColor(_blockchainTrustLevel)),
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
              ),
            ),

            const SizedBox(height: 20),

            // ═══════════════════════════════════════════════════════════
            // 💰 MESH TOKEN CARD
            // ═══════════════════════════════════════════════════════════
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 20),
              child: Card(
                elevation: 8,
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
                color: Colors.purple.shade50,
                child: Padding(
                  padding: const EdgeInsets.all(20),
                  child: Column(
                    children: [
                      Row(
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: [
                          Icon(Icons.token, color: Colors.purple.shade700, size: 30),
                          const SizedBox(width: 10),
                          const Text("MESH Token Rewards",
                              style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
                        ],
                      ),
                      const SizedBox(height: 15),
                      Row(
                        mainAxisAlignment: MainAxisAlignment.spaceEvenly,
                        children: [
                          _buildMeshStat("Balance", "${_meshBalance.toStringAsFixed(2)} MESH", Icons.account_balance_wallet),
                          _buildMeshStat("Relayed", "$_packetsRelayed pkts", Icons.swap_horiz),
                          _buildMeshStat("Tasks", "$_tasksCompleted done", Icons.check_circle),
                        ],
                      ),
                    ],
                  ),
                ),
              ),
            ),

            const SizedBox(height: 25),

            // ═══════════════════════════════════════════════════════════
            // STATS ROW
            // ═══════════════════════════════════════════════════════════
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceEvenly,
              children: [
                _buildSmallStat("Teyitler", _verifications.toString(), Colors.blue),
                _buildSmallStat("Yardımlar", _helps.toString(), Colors.green),
                _buildSmallStat("Local Score", _trustScore.toStringAsFixed(1), Colors.orange),
              ],
            ),

            const Divider(height: 40, indent: 20, endIndent: 20),

            // Activity History Section
            const Padding(
              padding: EdgeInsets.symmetric(horizontal: 20),
              child: Align(
                alignment: Alignment.centerLeft,
                child: Text("Aktivite Geçmişi",
                    style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
              ),
            ),

            SizedBox(
              height: 200,
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
            
            const SizedBox(height: 20),
          ],
        ),
      ),
    );
  }

  Widget _buildSmallStat(String label, String value, Color color) {
    return Column(
      children: [
        Text(value, style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold, color: color)),
        Text(label, style: const TextStyle(color: Colors.grey, fontWeight: FontWeight.w500)),
      ],
    );
  }

  Widget _buildMeshStat(String label, String value, IconData icon) {
    return Column(
      children: [
        Icon(icon, color: Colors.purple.shade400, size: 24),
        const SizedBox(height: 5),
        Text(value, style: const TextStyle(fontSize: 14, fontWeight: FontWeight.bold)),
        Text(label, style: TextStyle(fontSize: 11, color: Colors.grey.shade600)),
      ],
    );
  }
}