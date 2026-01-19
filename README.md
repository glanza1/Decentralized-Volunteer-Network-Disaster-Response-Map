# 🌐 Decentralized Disaster Response System

A **P2P-based disaster response coordination system** that requires no central server. Flutter map application + Python backend + Blockchain smart contracts.

![Architecture](schema.png)

---

## 🚀 Quick Start

### 1. Install Dependencies

```bash
# Python backend
pip install -r requirements.txt

# Flutter (if not installed)
# https://docs.flutter.dev/get-started/install
```

### 2. Start the Server

```bash
python main.py --no-ssl --no-auth
```

### 3. Access the Application

| Page | URL |
|------|-----|
| 🗺️ **Map Application** | http://localhost:8000/app/ |
| 📚 **API Documentation** | http://localhost:8000/docs |
| 🔐 **Wallet Page** | http://localhost:8000/static/wallet.html |

---

## 📱 Flutter Mobile/Web Application

### Features
- 🗺️ OpenStreetMap integration
- 📍 Create and view help requests
- ✅ Request verification and acceptance
- 👤 Blockchain-based digital identity
- 💰 MESH token reward system

### Web Build (Development)

```bash
flutter pub get
flutter build web --release --base-href /app/
```

### Entry Requirement
Only valid Ethereum addresses are accepted:
```
0xF018C3A8cfa5B17a36180a293092Ec884B8ecA61
```

---

## 🐍 Python Backend

### API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/help-request` | Create a help request |
| GET | `/api/local-requests` | List local requests |
| GET | `/api/nearby-requests` | Get nearby requests |
| GET | `/api/network/stats` | Network statistics |
| POST | `/api/wallet/create` | Create new wallet |
| POST | `/api/wallet/unlock` | Unlock wallet |
| GET | `/api/blockchain/identity/{addr}` | Volunteer identity |

### Modules

| File | Description |
|------|-------------|
| `main.py` | FastAPI application entry point |
| `api.py` | Help request REST API |
| `wallet.py` / `wallet_api.py` | HD Wallet (BIP-39, AES-256-GCM) |
| `p2p.py` | TCP/UDP P2P, Gossip protocol |
| `blockchain.py` / `blockchain_api.py` | Web3 smart contract integration |
| `ble.py` | Bluetooth Low Energy mesh (Linux) |
| `storage.py` | Thread-safe in-memory storage |
| `security.py` | API key authentication |

---

## 🔗 Smart Contracts (Solidity)

| Contract | Description |
|----------|-------------|
| `VolunteerIdentity.sol` | Soul-Bound NFT identity + reputation system |
| `TaskEscrow.sol` | Task creation, verification, completion |
| `AidDistribution.sol` | Donation pool + multi-signature |
| `MeshIncentive.sol` | P2P network contribution rewards (MESH token) |

### Start Blockchain (Optional)

```bash
cd blockchain
npx hardhat node
npx hardhat run scripts/deploy.js --network localhost
```

---

## 🏗️ Project Structure

```
├── main.py                 # FastAPI entry point
├── api.py                  # Help request API
├── wallet.py               # HD Wallet management
├── p2p.py                  # P2P network layer
├── blockchain.py           # Web3 integration
├── ble.py                  # Bluetooth mesh
├── lib/                    # Flutter source code
│   └── screens/
│       ├── welcome_screen.dart   # Wallet entry
│       ├── map_screen.dart       # Map
│       └── profile_screen.dart   # Digital identity
├── blockchain/
│   └── contracts/          # Solidity contracts
├── build/web/              # Flutter web build
└── .wallets/               # Encrypted wallets
```

---

## 🔒 Security

- **Wallet:** AES-256-GCM encryption, PBKDF2 key derivation
- **API:** API key authentication (optional)
- **Blockchain:** Trust level-based authorization
- **Frontend:** Ethereum address format validation

---

## 📡 Offline/Mesh Network

- **TCP/UDP:** Local network peer discovery and gossip protocol
- **BLE:** Bluetooth mesh communication (Linux, optional)
- **Store-and-Forward:** Message queuing when disconnected

---

## 📜 License

MIT License
