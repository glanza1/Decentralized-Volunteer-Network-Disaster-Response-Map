# Decentralized Disaster Response System

A P2P backend prototype for coordinating disaster response without central servers.

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                      NODE STRUCTURE                       │
├─────────────────────────────────────────────────────────┤
│  ┌─────────────┐    ┌──────────┐    ┌───────────────┐  │
│  │   FastAPI   │───▶│ Storage  │◀───│   P2P Layer   │  │
│  │   (api.py)  │    │          │    │   (p2p.py)    │  │
│  └─────────────┘    └──────────┘    └───────────────┘  │
│                           │                             │
│                     ┌─────▼─────┐                       │
│                     │  Models   │                       │
│                     │(models.py)│                       │
│                     └───────────┘                       │
└─────────────────────────────────────────────────────────┘
```

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Run the node
python main.py

# Access API docs
open http://localhost:8000/docs
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/help-request` | Create and broadcast a help request |
| GET | `/api/local-requests` | Get locally stored help requests |
| GET | `/api/nearby-requests` | Get requests near a location |
| GET | `/api/network/stats` | Get network statistics |

## Project Structure

- `main.py` - Application entry point
- `api.py` - FastAPI REST endpoints
- `p2p.py` - P2P networking layer (gossip-based)
- `models.py` - Pydantic data models
- `storage.py` - In-memory message storage

## Offline/Mesh Concepts

This prototype supports conceptual extensions for:
- **Bluetooth LE** - Device discovery and small messages
- **Wi-Fi Direct** - High-bandwidth ad-hoc networking
- **Store-and-Forward** - Message queuing when disconnected
