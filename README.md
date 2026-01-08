# Decentralized Disaster Response System

A comprehensive disaster response platform with both **Python backend** and **Flutter mobile app**.

---

## 🐍 Python Backend (P2P Server)

A P2P backend prototype for coordinating disaster response without central servers.


### Architecture

```
<img width="1024" height="559" alt="image" src="https://github.com/user-attachments/assets/d775df19-3890-4484-88cb![Uploading Gemini_Generated_Image_e3ojqee3ojqee3oj.png…]()
-e6d2dbf51beb" />
```

### Quick Start (Backend)

```bash
# Install dependencies
pip install -r requirements.txt

# Run the node
python main.py

# Access API docs
open http://localhost:8000/docs
```

### API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/help-request` | Create and broadcast a help request |
| GET | `/api/local-requests` | Get locally stored help requests |
| GET | `/api/nearby-requests` | Get requests near a location |
| GET | `/api/network/stats` | Get network statistics |

### Backend Project Structure

- `main.py` - Application entry point
- `api.py` - FastAPI REST endpoints
- `p2p.py` - P2P networking layer (gossip-based)
- `models.py` - Pydantic data models
- `storage.py` - In-memory message storage

### Offline/Mesh Concepts

This prototype supports conceptual extensions for:
- **Bluetooth LE** - Device discovery and small messages
- **Wi-Fi Direct** - High-bandwidth ad-hoc networking
- **Store-and-Forward** - Message queuing when disconnected

---

## 📱 Flutter Mobile App

A cross-platform mobile application for disaster response coordination.

### Quick Start (Mobile App)

```bash
# Navigate to Flutter project
cd lib/

# Install dependencies
flutter pub get

# Run the app
flutter run
```

### Mobile App Features

- Interactive map with disaster locations
- Volunteer profile management
- P2P network statistics
- Help request list view
