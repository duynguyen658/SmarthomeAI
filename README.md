<div align="center">
  <img src="logo.png" alt="SmartHome Logo" width="400">
</div>

# Smart Home AI Multi-Agent System

Production-ready smart home system built on event-driven architecture, rule engine, and AI-powered multi-agent system.

**Features:** Event-driven MQTT, Device State + Registry, Rule Engine, Memory AI (Qdrant + Redis)

## Table of Contents

- [Overview](#overview)
- [Features](#features)
- [System Architecture](#system-architecture)
- [Installation](#installation)
- [Configuration](#configuration)
- [Usage](#usage)
- [Project Structure](#project-structure)
- [Technology Stack](#technology-stack)
- [API Reference](#api-reference)
- [Troubleshooting](#troubleshooting)

## Overview

This is a **production-grade** smart home system featuring:

- **Event-Driven Architecture**: Centralized MQTT event bus for real-time device communication
- **Device Management**: Redis-backed state store with comprehensive device registry
- **Rule Engine**: Powerful automation engine with condition evaluation and action execution
- **Memory AI**: Vector database (Qdrant) for semantic search and AI learning
- **Local AI**: Ollama with Mistral for offline, private AI interactions

## Features

### Production Architecture

#### 1. Event-Driven MQTT System

Central event bus with publish-subscribe pattern:

```
smarthome/
├── devices/{device_uid}/state       # Device state (retained)
├── devices/{device_uid}/command     # Device commands
├── devices/{device_uid}/telemetry   # Sensor data
├── alerts/{severity}                 # Alert notifications
├── rules/{rule_id}/execution         # Rule execution logs
└── system/status                     # System health
```

**Features:**
- QoS support (0, 1, 2)
- Retained messages for state persistence
- Wildcard topic subscriptions
- Event type system with Pydantic models
- Async event handlers for devices, sensors, alerts

#### 2. Device State + Registry

**Device Registry** (PostgreSQL):
- Full CRUD operations
- Device metadata (capabilities, manufacturer, model)
- Device relationships (schedules, states, groups)
- UID-based identification

**State Store** (Redis):
- Fast key-value state access
- TTL-based expiration
- Sensor data caching
- Working memory for sessions

**State Machine**:
```
States: online ↔ offline ↔ on ↔ off ↔ error ↔ updating
Commands: connect, disconnect, turn_on, turn_off, toggle, recover
```

#### 3. Rule Engine

Flexible automation with condition-action model:

**Condition Types:**
- `device_state` - Check device status
- `sensor_value` - Numeric comparisons (>, <, ==, between)
- `time` - Time-based triggers
- `day_of_week` - Day filtering
- `state_change` - Detect state transitions

**Action Types:**
- `device_control` - Turn devices on/off
- `notification` - Send alerts
- `webhook` - HTTP callbacks
- `delay` - Wait between actions
- `scene` - Execute scenes
- `log` - Logging

**Trigger Types:**
- `event` - MQTT events
- `schedule` - Cron/daily/interval
- `manual` - API trigger

**Built-in Templates:**
- Auto Lights (turn on when dark)
- Gas Alert (dangerous gas detection)
- Night Mode (auto-off at night)
- Morning Routine (wake up automation)

#### 4. Memory AI

Four-tier memory system for AI agents:

| Memory Type | Storage | Purpose |
|------------|---------|---------|
| **Semantic** | Qdrant (Vector DB) | Facts, preferences, learned knowledge |
| **Episodic** | In-memory/DB | Event history, interactions |
| **Working** | Redis | Session context, conversation state |
| **Procedural** | Rule Engine | Automations, procedures |

**Features:**
- Semantic search with sentence transformers (all-MiniLM-L6-v2)
- Context building for AI prompts
- Learning from user interactions
- Preference extraction and storage
- Conversation history tracking

### AI Multi-Agent System

Built with Google ADK and Gemini 2.5 Flash:

1. **Host Agent** - Central coordinator, routes requests
2. **Home Assistant Agent** - Device control specialist
3. **Chef Agent** - Recipe and cooking suggestions
4. **Weather Agent** - Weather information
5. **Data Query Agent** - ThingsBoard sensor data

### Voice Control

- Wake word: "hey home" (Picovoice Porcupine)
- Vietnamese speech recognition
- Text-to-speech (Edge TTS)
- Multi-turn conversations

### Web Interface

- Dashboard with real-time sensor readings
- AI chat interface
- Device management
- Rule/automation creation UI
- Notification center

## System Architecture

```
                     ┌─────────────────┐
                     │   User Input    │
                     │ (Voice/Web/API) │
                     └────────┬────────┘
                              │
                              ▼
┌────────────────────────────────────────────────────────┐
│            FastAPI Backend (Port 8000)                 │
├────────────────────────────────────────────────────────┤
│  ┌──────────────────────────────────────────────────┐  │
│  │         Event Bus (MQTT Async Client)            │  │
│  │  ┌─────────┐  ┌─────────┐  ┌─────────┐           │  │
│  │  │ Device  │  │ Sensor  │  │  Alert  │           │  │
│  │  │ Handler │  │ Handler │  │ Handler │           │  │
│  │  └────┬────┘  └────┬────┘  └────┬────┘           │  │
│  │       │             │             │              │  │
│  └───────┼─────────────┼─────────────┼──────────────┘  │
│          │             │             │                 │
│          ▼             ▼             ▼                 │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐       │
│  │   Device    │ │   Sensor    │ │ Notification│       │
│  │   Registry  │ │  State Store│ │   Service   │       │
│  │  PostgreSQL │ │   (Redis)   │ │             │       │
│  └─────────────┘ └─────────────┘ └─────────────┘       │
│          │             │              │                │
│          └─────────────┼──────────────┘                │
│                        ▼                               │
│              ┌─────────────────┐                       │
│              │   Rule Engine   │                       │
│              │   (Automation)  │                       │
│              └────────┬────────┘                       │
│                       │                                │
│                       ▼                                │
│              ┌────────────────┐                        │
│              │    Memory AI   │                        │
│              │  Qdrant + Redis│                        │
│              └────────┬───────┘                        │
│                       │                                │
│                       ▼                                │
│              ┌─────────────────┐                       │
│              │   AI Agents     │                       │
│              │  (Gemini ADK)   │                       │
│              └─────────────────┘                       │
└────────────────────────────────────────────────────────┘
                         │
                         ▼
                  ┌─────────────┐
                  │   MQTT      │
                  │  Broker     │
                  └─────────────┘
                         │
                         ▼
                  ┌─────────────┐
                  │  Devices    │
                  │ (ESP32/etc) │
                  └─────────────┘
```

## Installation

### Prerequisites

- **Python 3.10+**
- **PostgreSQL** 12+
- **Redis** (optional, for state store)
- **Qdrant** (optional, for memory AI)
- **MQTT Broker** (e.g., Mosquitto)
- **Ollama** (for local AI - Mistral model)

### Step 1: Clone Repository

```bash
git clone <repository-url>
cd SmartHome_AiMutilAgent
```

### Step 2: Setup Virtual Environment

```bash
python -m venv Envi_venv

# Windows
Envi_venv\Scripts\activate

# Linux/macOS
source Envi_venv/bin/activate
```

### Step 3: Install Dependencies

```bash
pip install -r requirements.txt
```

**Core Dependencies:**
- `fastapi` - Web framework
- `uvicorn` - ASGI server
- `sqlalchemy` - ORM
- `psycopg2-binary` - PostgreSQL driver
- `aiomqtt` - Async MQTT client
- `redis` - Redis client
- `qdrant-client` - Vector database
- `sentence-transformers` - Embeddings
- `ollama` - Local AI client
- `httpx` - HTTP client for Ollama
- `pydantic-settings` - Configuration

### Step 3.5: Install Ollama (Local AI)

**Windows:**
1. Download Ollama from https://ollama.com/download
2. Install and run Ollama
3. Pull Mistral model:

```powershell
ollama pull mistral
```

**Linux/Mac:**
```bash
curl -fsSL https://ollama.com/install.sh | sh
ollama pull mistral
```

**Verify Ollama is running:**
```bash
ollama list
# Should show: mistral
```

**Start Ollama server (if not running):**
```bash
ollama serve
```

### Step 4: Setup Services (Docker Recommended)

```bash
# PostgreSQL
docker run --name smarthome-postgres \
  -e POSTGRES_PASSWORD=your_password \
  -e POSTGRES_DB=smarthome \
  -p 5432:5432 -d postgres

# Redis (State Store)
docker run --name smarthome-redis \
  -p 6379:6379 -d redis

# Qdrant (Vector DB - Optional)
docker run --name smarthome-qdrant \
  -p 6333:6333 -d qdrant/qdrant

# MQTT Broker (Mosquitto)
docker run --name smarthome-mqtt \
  -p 1883:1883 -p 9001:9001 \
  -v $(pwd)/mosquitto.conf:/mosquitto/config/mosquitto.conf \
  eclipse-mosquitto
```

### Step 5: Create Database

```bash
# Create PostgreSQL database
python scripts/create_db.py

# Initialize tables and migrate data
python database.py
```

### Step 6: Configure Environment

Create `.env` in project root:

```env
# ============================================
# LOCAL AI (Ollama) - PRIMARY
# ============================================
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=mistral
OLLAMA_TIMEOUT=120

# ============================================
# PostgreSQL Database
# ============================================
DB_HOST=localhost
DB_PORT=5432
DB_NAME=smarthome
DB_USER=postgres
DB_PASSWORD=your_password

# ============================================
# Redis (State Store)
# ============================================
REDIS_HOST=localhost
REDIS_PORT=6379

# ============================================
# Qdrant (Vector Store)
# ============================================
QDRANT_HOST=localhost
QDRANT_PORT=6333

# ============================================
# MQTT Broker
# ============================================
MQTT_BROKER=localhost
MQTT_PORT=1883
MQTT_CLIENT_ID=smarthome_backend

# ThingsBoard (Optional)
TB_URL=http://localhost:8080
TB_USER=your_email
TB_PASS=your_password

# Weather API
WEATHER_API_KEY=your_openweather_key

# Application
APP_NAME=SmartHome AI
APP_VERSION=2.0.0
DEBUG=false
LOG_LEVEL=INFO
```

## Usage

### Start Backend Server

```bash
python main.py
```

Server runs at: `http://localhost:8000`

**API Documentation:** `http://localhost:8000/docs`

### Start Voice Assistant (Optional)

```bash
python speakAi.py
```

Say "hey home" to activate.

### Access Web Interface

Open browser: `http://localhost:8000`

## API Reference

### Chat Endpoint

**POST** `/api/chat`

Send message to AI agent:

```json
{
  "query": "Bật đèn phòng khách",
  "user_id": "user_123",
  "session_id": "session_001"
}
```

**Response:**
```json
{
  "response": "Đã gửi lệnh bật đèn tại phòng khách.",
  "user_id": "user_123",
  "session_id": "session_001"
}
```

### Devices API

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/devices` | List all devices |
| GET | `/api/devices/{id}` | Get device details |
| POST | `/api/devices` | Create device |
| PUT | `/api/devices/{id}` | Update device |
| DELETE | `/api/devices/{id}` | Delete device |
| POST | `/api/devices/{id}/control` | Control device |

### Schedules API

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/schedules` | List schedules |
| POST | `/api/schedules` | Create schedule |
| PUT | `/api/schedules/{id}` | Update schedule |
| DELETE | `/api/schedules/{id}` | Delete schedule |
| POST | `/api/schedules/{id}/toggle` | Enable/disable |

### Rules API (Production)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/rules` | List all rules |
| POST | `/api/rules` | Create rule |
| GET | `/api/rules/{id}` | Get rule details |
| PUT | `/api/rules/{id}` | Update rule |
| DELETE | `/api/rules/{id}` | Delete rule |
| POST | `/api/rules/{id}/toggle` | Enable/disable |
| POST | `/api/rules/{id}/test` | Test rule |
| GET | `/api/rules/{id}/stats` | Rule statistics |
| GET | `/api/rules/{id}/history` | Execution history |

### Alerts API

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/alerts/rules` | List alert rules |
| POST | `/api/alerts/rules` | Create alert rule |
| PUT | `/api/alerts/rules/{id}` | Update alert rule |
| DELETE | `/api/alerts/rules/{id}` | Delete alert rule |
| GET | `/api/alerts/notifications` | Get notifications |
| POST | `/api/alerts/notifications/{id}/read` | Mark as read |

## Project Structure

```
SmartHome_AiMutilAgent/
│
├── main.py                          # FastAPI application entry point
├── database.py                      # PostgreSQL models & setup
├── scheduler.py                     # APScheduler for automation
├── notification_service.py          # Alert/notification service
├── speakAi.py                       # Voice assistant with wake word
├── requirements.txt                 # Python dependencies
├── .env                            # Environment variables
├── .gitignore                      # Git ignore rules
│
├── core/                           # Core utilities (Phase 0)
│   ├── __init__.py
│   ├── config.py                   # Configuration management (Pydantic Settings)
│   ├── exceptions.py               # Custom exception hierarchy
│   └── logging.py                  # Structured logging setup
│
├── events/                         # Event-driven system (Phase 1)
│   ├── __init__.py
│   ├── types.py                    # Event type definitions (Pydantic models)
│   ├── event_bus.py                # MQTT event bus singleton
│   ├── publisher.py                # Event publisher utilities
│   ├── subscriber.py               # Event subscriber base
│   ├── device_events.py            # Device event factories
│   ├── sensor_events.py            # Sensor event factories
│   ├── system_events.py            # System event factories
│   └── handlers/                   # Event handlers
│       ├── __init__.py
│       ├── device_handler.py       # Device state/command handling
│       ├── sensor_handler.py       # Sensor data & threshold alerts
│       └── alert_handler.py        # Alert management & notifications
│
├── devices/                        # Device management (Phase 2)
│   ├── __init__.py
│   ├── registry.py                 # Device registry (CRUD + control)
│   ├── state_store.py              # Redis-backed state store
│   ├── state_machine.py            # State machine & transitions
│   ├── groups.py                   # Device group management
│   └── capabilities.py             # Capability definitions
│
├─ rules/                           # Rule engine (Phase 3)
│   ├── __init__.py
│   ├── models.py                   # Rule, Condition, Action models
│   ├── engine.py                   # Rule engine core
│   ├── conditions.py               # Condition evaluators
│   ├── actions.py                  # Action executors
│   ├── triggers.py                 # Trigger handlers
│   ├── scheduler.py                # Schedule-based triggers
│   ├── logger.py                   # Execution logging
│   └── templates.py                # Rule templates
│
├── memory/                         # Memory AI system (Phase 4)
│   ├── __init__.py
│   ├── vector_store.py             # Qdrant vector store wrapper
│   ├── semantic_memory.py          # Semantic memory (facts, preferences)
│   ├── episodic_memory.py          # Episodic memory (event history)
│   ├── working_memory.py           # Working memory (session context)
│   ├── procedural_memory.py        # Procedural memory (skills)
│   ├── context.py                  # Context builder for AI
│   ├── embeddings.py               # Embedding generation
│   └── memory_system.py            # Unified memory interface
│
├── api/                            # REST API endpoints
│   ├── __init__.py
│   ├── devices.py                  # Device management API
│   ├── schedules.py                # Scheduling API
│   ├── alerts.py                   # Alerts & notifications API
│   └── rules.py                    # Rules API (Phase 3)
│
├── smart_home/                     # AI Agents (Google ADK)
│   ├── __init__.py
│   ├── agent.py                    # Multi-agent definitions
│   ├── tools.py                    # Agent tools
│   └── prompts.py                  # Agent prompts
│
├── tools/                          # Utility tools
│   ├── __init__.py
│   ├── controlDevice.py            # MQTT device control
│   ├── rqThingsboard.py            # ThingsBoard API client
│   └── weather.py                  # Weather API integration
│
├── web/                            # Frontend web interface
│   ├── index.html                  # Main HTML
│   ├── styles.css                  # Global styles
│   ├── app.js                      # Main JavaScript
│   ├── device-management.js        # Device management UI
│   ├── automation.js               # Automation/rules UI
│   ├── alerts.js                   # Alerts UI
│   ├── notifications.js            # Notification center
│   └── README.md                   # Frontend documentation
│
├── scripts/                        # Utility scripts
│   ├── create_db.py                # Database creation script
│   ├── migrate.py                  # Data migration
│   └── backup.sh                   # Backup utilities
│
├── config/                         # Configuration files
│   ├── node_red.json              # Node-RED flows (if used)
│   └── logging.yaml               # Logging configuration
│
├── hardware/                       # Hardware code
│   └── Smart_Home_Project.ino      # Arduino/ESP32 firmware
│
├── sounds/                         # Audio files
│   └── google_home_beep.wav       # Wake word feedback
│
├── keyword/                        # Picovoice keyword files
│   └── hey-home_en_windows_v3_0_0.ppn
│
├── logs/                           # Application logs (created at runtime)
│   ├── app.log
│   ├── error.log
│   └── access.log
│
├── tests/                          # Unit & integration tests
│   ├── __init__.py
│   ├── test_events.py
│   ├── test_devices.py
│   ├── test_rules.py
│   ├── test_memory.py
│   └── conftest.py
│
├── docker/                         # Docker configurations
│   ├── Dockerfile
│   ├── docker-compose.yml
│   └── .dockerignore
│
├── docs/                           # Documentation
│   ├── architecture.md
│   ├── api.md
│   └── deployment.md
│
└── README.md                       # This file
```

## Technology Stack

### Backend & AI
| Technology | Version | Purpose |
|-----------|---------|---------|
| Python | 3.10+ | Runtime |
| FastAPI | >=0.104.0 | REST API framework |
| Uvicorn | >=0.24.0 | ASGI server |
| Google ADK | >=0.1.0 | Multi-agent framework |
| Gemini 2.5 Flash | - | LLM model |
| SQLAlchemy | >=2.0.0 | ORM |
| PostgreSQL | 12+ | Primary database |
| Redis | 5+ | State store & cache |
| Qdrant | 1.7+ | Vector database |

### IoT & Messaging
| Technology | Purpose |
|-----------|---------|
| aiomqtt | Async MQTT client |
| Paho MQTT | Legacy MQTT client |
| ThingsBoard | IoT platform integration |

### Machine Learning
| Library | Purpose |
|---------|---------|
| sentence-transformers | Text embeddings (all-MiniLM-L6-v2) |
| numpy | Numerical operations |
| scikit-learn | ML utilities |

### Frontend
| Technology | Purpose |
|-----------|---------|
| HTML5/CSS3 | User interface |
| JavaScript (ES6+) | Client-side logic |
| WebSocket | Real-time updates |
| Fetch API | HTTP requests |

### Voice
| Technology | Purpose |
|-----------|---------|
| Picovoice Porcupine | Wake word detection |
| SpeechRecognition | Speech-to-text |
| Edge TTS | Text-to-speech |
| PyAudio | Audio I/O |

### DevOps
| Tool | Purpose |
|------|---------|
| Docker | Containerization |
| Docker Compose | Multi-service orchestration |
| APScheduler | Task scheduling |
| python-dotenv | Environment management |

## API Examples

### Create Rule Example

```json
{
  "name": "Auto Fan When Hot",
  "description": "Turn on fan when temperature exceeds 30°C",
  "enabled": true,
  "priority": 10,
  "conditions": [
    {
      "type": "sensor_value",
      "sensor_type": "temperature",
      "operator": "gt",
      "value": 30
    }
  ],
  "condition_logic": "AND",
  "actions": [
    {
      "type": "device_control",
      "device_type": "fan",
      "command": "on"
    }
  ],
  "trigger": {
    "type": "event",
    "event_types": ["sensor.data"]
  },
  "cooldown_seconds": 300
}
```

### Create Alert Rule Example

```json
{
  "name": "High Temperature Alert",
  "sensor_type": "temperature",
  "condition": "gt",
  "threshold_value": 35.0,
  "enabled": true,
  "notification_type": "browser"
}
```

## Deployment

### Using Docker Compose

```yaml
# docker-compose.yml
version: '3.8'

services:
  postgres:
    image: postgres:15
    environment:
      POSTGRES_PASSWORD: ${DB_PASSWORD}
      POSTGRES_DB: smarthome
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

  qdrant:
    image: qdrant/qdrant:latest
    ports:
      - "6333:6333"

  mosquitto:
    image: eclipse-mosquitto:2
    volumes:
      - ./mosquitto.conf:/mosquitto/config/mosquitto.conf
    ports:
      - "1883:1883"
      - "9001:9001"

  app:
    build: .
    command: python main.py
    volumes:
      - .:/app
    ports:
      - "8000:8000"
    depends_on:
      - postgres
      - redis
      - qdrant
      - mosquitto
    env_file:
      - .env

volumes:
  postgres_data:
```

### Production Considerations

1. **Security:**
   - Use HTTPS/TLS
   - Secure MQTT with SSL/TLS
   - Environment variables for secrets
   - API rate limiting

2. **Scalability:**
   - Multiple API workers (uvicorn --workers)
   - Redis cluster for high availability
   - Qdrant cluster for vector search
   - Database connection pooling

3. **Monitoring:**
   - Application logs (structured JSON)
   - Metrics collection (Prometheus)
   - Health check endpoints
   - Alert rules for system status

4. **Backup:**
   - Daily PostgreSQL backups
   - Redis RDB/AOF persistence
   - Qdrant snapshot backups

## Troubleshooting

### Database Connection Error

```
OperationalError: connection to server at "localhost" failed
```

**Solution:**
1. Ensure PostgreSQL is running:
   ```bash
   # Windows
   net start postgresql

   # Docker
   docker start smarthome-postgres
   ```

2. Check credentials in `.env`

3. Create database:
   ```bash
   python scripts/create_db.py
   ```

### Redis/Qdrant Not Available

System automatically falls back to in-memory mock implementations.

**To enable:**
```bash
# Redis
docker run -p 6379:6379 redis

# Qdrant
docker run -p 6333:6333 qdrant/qdrant
```

### MQTT Connection Failed

1. Check broker address/port in `.env`
2. Ensure broker is running
3. Check firewall/network settings

### Import Errors

```bash
# Reinstall dependencies
pip install -r requirements.txt --force-reinstall

# Clear __pycache__
find . -type d -name __pycache__ -exec rm -r {} +
```

### Port Already in Use

```bash
# Find process using port 8000
netstat -ano | findstr :8000

# Kill process
taskkill /PID <pid> /F
```

## Development

### Running Tests

```bash
pytest tests/
```

### Code Style

```bash
# Format code
black ./

# Lint
flake8

# Type checking
mypy .
```

### Adding New Rules

1. Define rule in `rules/models.py` or via API
2. Implement condition evaluator in `rules/conditions.py`
3. Implement action executor in `rules/actions.py`
4. Add API endpoints in `api/rules.py`

### Adding New Event Types

1. Add to `events/types.py` EventType enum
2. Create event model class
3. Add handler in `events/handlers/`
4. Register with event bus

## License

[MIT License](LICENSE)

## Contributors

Contributions welcome! Please open issues and PRs.

## Support

For issues, questions, or feature requests, please open an issue on GitHub.

---

**Note:** This is a production-ready system. For production deployment:
- Use environment variables for all secrets
- Enable TLS/SSL for all services
- Set up proper monitoring & logging
- Configure backup strategies
- Implement authentication/authorization
- Follow security best practices
