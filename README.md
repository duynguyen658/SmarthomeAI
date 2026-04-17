<div align="center">
  <img src="logo.png" alt="SmartHome Logo" width="400">
</div>

# Smart Home AI Multi-Agent System

Hệ thống nhà thông minh sử dụng AI đa tác tử (Multi-Agent) để điều khiển thiết bị, giám sát cảm biến và tương tác với người dùng thông qua giọng nói hoặc giao diện web.

**Phiên bản Production** với Event-driven Architecture, Rule Engine, và Memory AI.

## Muc Luc

- [Tong Quan](#tong-quan)
- [Tinh Nang](#tinh-nang)
- [Kien Truc He Thong](#kien-truc-he-thong)
- [Cai Dat](#cai-dat)
- [Cau Hinh](#cau-hinh)
- [Su Dung](#su-dung)
- [Cau Truc Du An](#cau-truc-du-an)
- [Cong Nghe Su Dung](#cong-nghe-su-dung)

## Tong Quan

Day la he thong nha thong minh production-ready, xay dung tren:

- **Event-driven Architecture**: MQTT-based event bus cho real-time communication
- **Device State Management**: Redis-backed state store voi device registry
- **Rule Engine**: Automation engine voi condition evaluation va action execution
- **Memory AI**: Vector store (Qdrant) cho semantic memory va learning
- **Multi-Agent System**: Google ADK voi Gemini cho AI-powered interactions

## Tinh Nang

### Production Features

#### 1. Event-Driven MQTT Architecture

- **MQTT Event Bus**: Central event hub voi pub/sub pattern
- **Topic Hierarchy**: Chuẩn hóa topic structure
  ```
  smarthome/
  ├── devices/{device_uid}/state
  ├── devices/{device_uid}/command
  ├── devices/{device_uid}/telemetry
  ├── alerts/{severity}
  ├── rules/{rule_id}/execution
  └── system/status
  ```
- **QoS Support**: Quality of Service levels (0, 1, 2)
- **Retained Messages**: Device state persistence
- **Event Handlers**: Device, Sensor, Alert handlers

#### 2. Device State + Registry

- **Device Registry**: CRUD operations cho devices trong PostgreSQL
- **State Store**: Redis-backed state management voi TTL
- **State Machine**: Valid state transitions validation
  - States: online, offline, on, off, error, updating
  - Commands: connect, disconnect, turn_on, turn_off, toggle
- **Capabilities**: Device capability definitions
- **Device Groups**: Logical grouping cua devices

#### 3. Rule Engine

Automation engine voi flexible condition-action model:

- **Condition Types**:
  - Device state conditions
  - Sensor value conditions (>, <, ==, between)
  - Time-based conditions
  - Day of week conditions
  - State change conditions

- **Action Types**:
  - Device control (on/off)
  - Notifications (browser, push)
  - Webhooks (HTTP calls)
  - Delays
  - Scenes
  - Logging

- **Trigger Types**:
  - Event-driven (MQTT events)
  - Schedule-based (cron, daily, interval)
  - Manual trigger

- **Rule Templates**:
  - Auto lights
  - Gas alert
  - Night mode
  - Morning routine

#### 4. Memory AI

Four-tier memory system cho AI agents:

- **Semantic Memory**: Facts, preferences, habits (Qdrant vector store)
- **Episodic Memory**: Event history, interaction records
- **Working Memory**: Current session context (Redis)
- **Procedural Memory**: Rules, automations, procedures

Features:
- Semantic search voi embeddings
- Context building cho AI prompts
- Learning from interactions
- Preference extraction

### AI Multi-Agent System

1. **Host Agent** - Root coordinator
2. **Home Assistant Agent** - Device control
3. **Chef Agent** - Recipe suggestions
4. **Weather Agent** - Weather info
5. **Data Query Agent** - Sensor data from ThingsBoard

### Voice Control

- Wake word: "hey home"
- Vietnamese speech recognition
- Edge TTS for responses

### Web Interface

- Dashboard voi sensor readings
- AI chat interface
- Device management
- Automation scheduling
- Alert rules & notifications
- Rules management (Production feature)

## Kien Truc He Thong

```
User Input
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│                    Event Bus (MQTT)                          │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐       │
│  │ Device  │  │ Sensor  │  │  Alert  │  │  Rule   │       │
│  │ Handler │  │ Handler │  │ Handler │  │ Engine  │       │
│  └────┬────┘  └────┬────┘  └────┬────┘  └────┬────┘       │
│       │             │             │             │          │
└───────┼─────────────┼─────────────┼─────────────┼──────────┘
        │             │             │             │
        ▼             ▼             ▼             ▼
┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐
│   Device    │ │   Sensor    │ │ Notification│ │    Rule     │
│   Registry  │ │  State Store│ │   Service   │ │   Engine    │
│  (PostgreSQL)│ │   (Redis)   │ │             │ │             │
└─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘
        │             │                           │
        └─────────────┼───────────────────────────┘
                      ▼
              ┌─────────────┐
              │    Memory    │
              │   AI System  │
              │   (Qdrant)   │
              └─────────────┘
                      │
                      ▼
              ┌─────────────┐
              │     AI      │
              │   Agents    │
              │  (Gemini)   │
              └─────────────┘
```

## Cai Dat

### Yeu Cau

- Python 3.10+
- PostgreSQL
- Redis (cho state store)
- Qdrant (cho vector store, optional)
- MQTT Broker

### Buoc 1: Clone va Setup

```bash
git clone <repository-url>
cd SmartHome_AiMutilAgent
python -m venv Envi_venv
Envi_venv\Scripts\activate  # Windows
# source Envi_venv/bin/activate  # Linux/macOS
```

### Buoc 2: Database Setup

**PostgreSQL:**
```bash
docker run --name smarthome-postgres \
  -e POSTGRES_PASSWORD=your_password \
  -e POSTGRES_DB=smarthome \
  -p 5432:5432 -d postgres
```

**Redis (Optional - cho State Store):**
```bash
docker run --name smarthome-redis -p 6379:6379 -d redis
```

**Qdrant (Optional - cho Memory AI):**
```bash
docker run --name smarthome-qdrant -p 6333:6333 -d qdrant/qdrant
```

### Buoc 3: Dependencies

```bash
pip install -r requirements.txt
```

### Buoc 4: Database Init

```bash
python database.py
```

## Cau Hinh

Tao file `.env`:

```env
# Google Gemini API
GOOGLE_API_KEY=your_google_api_key

# PostgreSQL
DB_HOST=localhost
DB_PORT=5432
DB_NAME=smarthome
DB_USER=postgres
DB_PASSWORD=your_password

# Redis (Optional)
REDIS_HOST=localhost
REDIS_PORT=6379

# Qdrant (Optional)
QDRANT_HOST=localhost
QDRANT_PORT=6333

# MQTT
MQTT_BROKER=10.0.18.255
MQTT_PORT=1883

# ThingsBoard
TB_URL=http://10.0.18.255:8080
TB_USER=your_email
TB_PASS=your_password

# Weather API
WEATHER_API_KEY=your_weather_api_key
```

## Su Dung

### Khoi Dong Backend

```bash
python main.py
```

Server chay tai `http://localhost:8000`

### API Endpoints

#### Chat API
```
POST /api/chat
```

#### Devices
```
GET  /api/devices
POST /api/devices
PUT  /api/devices/{id}
DELETE /api/devices/{id}
POST /api/devices/{id}/control
```

#### Schedules
```
GET  /api/schedules
POST /api/schedules
PUT  /api/schedules/{id}
DELETE /api/schedules/{id}
POST /api/schedules/{id}/toggle
```

#### Alerts
```
GET  /api/alerts/rules
POST /api/alerts/rules
GET  /api/alerts/notifications
POST /api/alerts/notifications/{id}/read
```

#### Rules (Production)
```
GET  /api/rules              # List all rules
POST /api/rules              # Create rule
GET  /api/rules/{id}        # Get rule
PUT  /api/rules/{id}        # Update rule
DELETE /api/rules/{id}      # Delete rule
POST /api/rules/{id}/toggle # Enable/disable
POST /api/rules/{id}/test   # Test rule
GET  /api/rules/{id}/stats  # Rule statistics
```

### Rule Example

```json
{
  "name": "Auto Fan",
  "description": "Turn on fan when hot",
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

## Cau Truc Du An

```
SmartHome_AiMutilAgent/
|
├── main.py                    # FastAPI entry point
├── database.py               # PostgreSQL models
├── scheduler.py               # APScheduler
├── notification_service.py     # Alert service
├── speakAi.py                # Voice assistant
├── requirements.txt
|
├── core/                     # Core utilities
│   ├── __init__.py
│   ├── config.py             # Configuration management
│   ├── exceptions.py         # Custom exceptions
│   └── logging.py            # Logging setup
|
├── events/                   # Event-driven system
│   ├── __init__.py
│   ├── types.py              # Event type definitions
│   ├── event_bus.py          # MQTT event bus
│   └── handlers/
│       ├── device_handler.py
│       ├── sensor_handler.py
│       └── alert_handler.py
|
├── devices/                  # Device management
│   ├── __init__.py
│   ├── state_store.py        # Redis state store
│   ├── registry.py           # Device registry
│   └── state_machine.py     # State machine
|
├── rules/                    # Rule engine
│   ├── __init__.py
│   ├── models.py             # Rule models
│   ├── engine.py             # Rule engine core
│   ├── conditions.py         # Condition evaluators
│   ├── actions.py            # Action executors
│   └── scheduler.py          # Schedule triggers
|
├── memory/                   # Memory AI
│   ├── __init__.py
│   ├── vector_store.py       # Qdrant vector store
│   ├── semantic_memory.py     # Semantic memory
│   ├── episodic_memory.py     # Episodic memory
│   ├── working_memory.py     # Working memory
│   └── memory_system.py       # Unified interface
|
├── api/                      # REST API
│   ├── __init__.py
│   ├── devices.py
│   ├── schedules.py
│   ├── alerts.py
│   └── rules.py             # Rules API
|
├── smart_home/               # AI Agents
│   └── agent.py
|
├── tools/                    # Utility tools
│   ├── controlDevice.py
│   ├── rqThingsboard.py
│   └── weather.py
|
└── web/                      # Frontend
    ├── index.html
    ├── styles.css
    ├── app.js
    └── ...
```

## Cong Nghe Su Dung

### Backend & AI
| Technology | Purpose |
|-----------|---------|
| FastAPI | REST API |
| Google ADK | Multi-agent framework |
| Gemini 2.5 Flash | LLM |
| PostgreSQL | Database |
| SQLAlchemy | ORM |
| Redis | State Store |
| Qdrant | Vector DB |
| aiomqtt | Async MQTT |
| APScheduler | Scheduling |

### Frontend
| Technology | Purpose |
|-----------|---------|
| HTML/CSS/JavaScript | SPA |
| WebSocket | Real-time |

### IoT
| Technology | Purpose |
|-----------|---------|
| Paho MQTT | MQTT client |
| ThingsBoard | IoT platform |
| ESP32 | Hardware |

## Troubleshooting

### Redis/Qdrant Not Available
He thong se tu dong su dung mock implementations khi Redis/Qdrant khong kha dung.

### MQTT Connection Failed
Kiem tra broker address va port trong .env.

### Database Connection
Dam bao PostgreSQL dang chay va credentials dung trong .env.

## License

[Thong tin license]

## Contributors

[Thong tin contributors]
