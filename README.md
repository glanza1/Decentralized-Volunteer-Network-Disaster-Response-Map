# 🌐 Decentralized Disaster Response System

A **P2P-based disaster response coordination system** that requires no central server. Flutter map application + Python backend + Blockchain smart contracts.

![Architecture](schema.png)

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
Only valid Ethereum addresses are accepted, test adress is below:
```
0xF018C3A8cfa5B17a36180a293092Ec884B8ecA61
```

---

## 🐍 Python Backend Details

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
| POST | `/api/{id}/verify` | Verify request on blockchain |
| POST | `/api/{id}/accept` | Accept a help request |
| POST | `/api/{id}/complete` | Complete a help request |

### Main Modules

#### `main.py`
- Creates FastAPI application
- Starts P2P node
- SSL/TLS support (optional)
- Configuration via command-line arguments

#### `api.py`
REST API endpoints for help requests, network stats, and blockchain-integrated actions.

#### `p2p.py`
- **TCP Server/Client**: Peer-to-peer messaging
- **UDP Broadcast**: Local network peer discovery
- **Gossip Protocol**: Epidemic message dissemination
- **BLE Integration**: Bluetooth mesh support

#### `wallet.py`
- **HD Wallet**: BIP-39 mnemonic wallet creation
- **Encryption**: AES-256-GCM, PBKDF2 key derivation
- **Operations**: Message and transaction signing
- **Storage**: Encrypted JSON in `.wallets/` directory

#### `blockchain.py`
- VolunteerIdentity: Volunteer registration, trust levels
- TaskEscrow: Task management and verification
- AidDistribution: Donation pool, multi-sig
- MeshIncentive: MESH token rewards

#### `models.py`
Data models:
- `HelpRequest`: Main help request message
- `GeoLocation`: GPS coordinates
- `NodeIdentity`: Cryptographic node identity
- `RequestType`: MEDICAL, RESCUE, SHELTER, FOOD_WATER, TRANSPORT, INFO
- `RequestPriority`: CRITICAL, HIGH, MEDIUM, LOW

---

## 📱 Flutter Frontend Details

### Screens (`lib/screens/`)

| File | Description |
|------|-------------|
| `welcome_screen.dart` | Ethereum address login |
| `map_screen.dart` | OpenStreetMap map view |
| `profile_screen.dart` | Digital identity and statistics |
| `list_screen.dart` | Help requests list |
| `statistics_screen.dart` | Network statistics |

### Services (`lib/services/`)

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


## 📦 Dependencies

### Python (`requirements.txt`)
```
fastapi>=0.104.0       # Web framework
uvicorn>=0.24.0        # ASGI server
pydantic>=2.5.0        # Data validation
bleak>=0.22.0          # BLE client
mnemonic>=0.20         # BIP-39 mnemonic
cryptography>=41.0.0   # Encryption
web3>=6.0.0            # Ethereum
eth-account>=0.10.0    # Account management
```

### Blockchain (`blockchain/package.json`)
- Hardhat development environment
- OpenZeppelin contracts

---

## 🚀 Running Commands

### Start Backend
```bash
# Install dependencies
pip install -r requirements.txt

# Start server (without SSL and auth)
python main.py --no-ssl --no-auth
```

### Flutter Web Build
```bash
flutter pub get
flutter build web --release --base-href /app/
```

### Start Blockchain (Optional)
```bash
cd blockchain
npx hardhat node              # Start local node
npx hardhat run scripts/deploy.js --network localhost
```

### Access URLs

| Page | URL |
|------|-----|
| 🗺️ Map Application | http://localhost:8000/app/ |
| 📚 API Documentation | http://localhost:8000/docs |
| 🔐 Wallet Page | http://localhost:8000/static/wallet.html |

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

