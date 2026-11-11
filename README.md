# Multi-Application Notification Gateway

Enterprise-grade, secure, multi-tenant notification gateway built with **Python 3.12+**, **FastAPI**, **Pydantic v2**, and **SQLAlchemy 2.0**. It exposes a unified API that allows external client applications to dispatch notifications via **Telegram Bot API** and **Google Gmail API** with rate limiting, tenant isolation, idempotency, and automated retries.

---

## 🏗️ Architecture Overview

The gateway is built following clean architectural principles:

```
                      +---------------------------------------+
                      |       Client Applications / SDKs      |
                      +-------------------+-------------------+
                                          |
                               [X-API-Key | HTTPS]
                                          v
                      +---------------------------------------+
                      |            FastAPI Gateway            |
                      |  - Security & Rate Limiting Middleware|
                      |  - Structured Logging & Redaction     |
                      +-------------------+-------------------+
                                          |
                      +-------------------+-------------------+
                      |             API Layer                 |
                      |  /api/v1/notifications                |
                      |  /api/v1/admin/*                      |
                      |  /health | /metrics                   |
                      +-------------------+-------------------+
                                          |
                      +-------------------+-------------------+
                      |      Business Logic / Services        |
                      |  - NotificationService (Retry/Jitter) |
                      |  - AuthService (HMAC + Pepper)        |
                      |  - EncryptionService (AES-256-GCM)    |
                      +-------------------+-------------------+
                                          |
                     +--------------------+--------------------+
                     |                                         |
                     v                                         v
        +-------------------------+               +-------------------------+
        |    Telegram Provider    |               |      Gmail Provider     |
        |  - HTML & MarkdownV2    |               |  - Google OAuth2 Flow   |
        |  - Inline Keyboards     |               |  - Auto Token Refresh   |
        |  - Exponential Backoff  |               |  - MIME & Attachments   |
        +-------------------------+               +-------------------------+
                     |                                         |
                     v                                         v
            Telegram Bot API                           Gmail REST API
```

### Directory Structure
```
notify/
├── app/
│   ├── api/
│   │   ├── deps.py                       # FastAPI dependencies (DB, Auth, Admin)
│   │   └── v1/
│   │       ├── router.py                 # Consolidated API v1 router
│   │       └── endpoints/
│   │           ├── notifications.py      # Client notification dispatch endpoints
│   │           ├── health.py             # Health check endpoints
│   │           ├── metrics.py            # Prometheus metrics (/metrics)
│   │           └── admin/
│   │               ├── applications.py   # Application & API key CRUD
│   │               ├── telegram_configs.py # Telegram configuration CRUD & test
│   │               ├── gmail_configs.py  # Gmail OAuth & configuration CRUD & test
│   │               └── audit.py          # Audit log query endpoint
│   ├── core/
│   │   ├── config.py                     # Pydantic Settings configuration
│   │   ├── security.py                   # API Key generation, HMAC-SHA256 with pepper
│   │   ├── encryption.py                 # AES-256-GCM encryption & key rotation
│   │   ├── exceptions.py                 # Custom domain exception hierarchy
│   │   ├── logging.py                    # Structured JSON logging with redaction
│   │   └── rate_limiter.py               # Redis & in-memory sliding window rate limiter
│   ├── database/
│   │   ├── base.py                       # SQLAlchemy 2.0 Base & Mixins
│   │   └── session.py                    # AsyncSession database engine
│   ├── models/                           # SQLAlchemy 2.0 entities
│   │   ├── application.py
│   │   ├── api_key.py
│   │   ├── permission.py
│   │   ├── telegram_config.py
│   │   ├── gmail_config.py
│   │   ├── notification.py
│   │   └── audit_log.py
│   ├── schemas/                          # Pydantic v2 validation schemas
│   ├── repositories/                     # Repository pattern database access
│   ├── providers/                        # External notification providers
│   │   ├── base.py                       # Base notification provider interface
│   │   ├── telegram.py                   # Telegram Bot API implementation
│   │   └── gmail.py                      # Gmail REST API v1 implementation
│   ├── services/                         # Core domain services
│   └── middleware/
│       ├── security_headers.py           # HSTS, CSP, nosniff headers
│       └── logging_middleware.py         # Request tracing without sensitive leakage
├── alembic/                              # Alembic async database migrations
├── tests/
│   ├── unit/                             # Cryptography, security, and provider tests
│   └── integration/                      # API endpoints, idempotency, retry tests
├── Dockerfile                            # Multi-stage production Dockerfile
├── docker-compose.yml                    # PostgreSQL + Redis + Gateway stack
├── init_db.py                            # Database migration & bootstrap script
├── pyproject.toml                        # Project metadata & dependencies
└── .env.example                          # Environment configuration template
```

---

## 🔒 Security Model & Cryptography

### 1. AES-256-GCM Encryption at Rest
All sensitive secrets (Telegram Bot Tokens, Google OAuth Client Secrets, Refresh Tokens, Access Tokens) are encrypted before insertion into the database using AES-256-GCM authenticated encryption.

* **Format**: `{version}:{nonce_b64}:{ciphertext_b64}`
* **Key Rotation Strategy**: Supports key versioning (`v1`, `v2`, etc.). Old records can be decrypted with earlier keys from the key ring, and re-encrypted to the active version on-the-fly.

### 2. Cryptographic API Key Management
* **Prefix-Secret Format**: `ng_live_<prefix_8>_<secret_32>` (e.g. `ng_live_a1b2c3d4_kL92m...`).
* **Storage**: The public prefix is indexed for fast $O(1)$ database lookup. The secret part is stored strictly as an **HMAC-SHA256 hash using a secret pepper** (`API_KEY_PEPPER`).
* **Exposure**: The raw API Key is shown **ONLY ONCE** upon creation or regeneration.
* **Revocation**: Keys can be immediately revoked at any time.

### 3. Multi-Tenant Isolation
* Every client request authenticated with `X-API-Key` is strictly scoped to its own `application_id`.
* An application cannot read, update, or dispatch through another application's Telegram or Gmail configuration.
* Listing notifications (`GET /api/v1/notifications`) returns only notifications belonging to the calling application.

### 4. Automatic Sensitive Data Redaction
* Structured JSON logger applies regular-expression masking to all log entries, guaranteeing that tokens, API keys, passwords, and authorization headers are never logged to console or storage.

---

## 🚀 Installation & Setup

### Prerequisites
* Python 3.12+ (or Docker & Docker Compose)
* PostgreSQL (or SQLite for development)
* Redis (optional, in-memory sliding window fallback is enabled by default)

### Local Development Setup

1. **Clone and navigate to repository**:
   ```bash
   cd notify
   ```

2. **Create and activate virtual environment**:
   ```bash
   python -m venv .venv
   # Windows:
   .venv\Scripts\activate
   # Linux/macOS:
   source .venv/bin/activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -e ".[dev]"
   ```

4. **Configure environment**:
   ```bash
   cp .env.example .env
   ```
   Generate master encryption keys:
   ```bash
   python -c "import secrets, base64; print('MASTER_ENCRYPTION_KEY=' + base64.urlsafe_b64encode(secrets.token_bytes(32)).decode())"
   python -c "import secrets; print('API_KEY_PEPPER=' + secrets.token_hex(32))"
   python -c "import secrets; print('ADMIN_API_KEY=' + secrets.token_urlsafe(32))"
   ```

5. **Run database migrations and bootstrap initial application**:
   ```bash
   alembic upgrade head
   python init_db.py
   ```
   *Note: Save the generated initial API key printed by `init_db.py`.*

6. **Start the API Server**:
   ```bash
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```
   Interactive Swagger documentation is available at: **http://localhost:8000/docs**

---

## 🐳 Docker Deployment

To launch the complete production stack (PostgreSQL 16 + Redis 7 + Notification Gateway):

```bash
docker-compose up -d --build
```

Check logs:
```bash
docker-compose logs -f gateway
```

---

## 📖 Configuration Guides

### 1. Telegram Bot Integration
1. Open Telegram and talk to [@BotFather](https://t.me/BotFather).
2. Run `/newbot` and follow instructions to obtain your **Bot Token** (e.g. `7123456789:AAH...`).
3. Create a configuration in the Gateway using the Admin API:
   ```bash
   curl -X POST http://localhost:8000/api/v1/admin/telegram \
     -H "X-Admin-API-Key: YOUR_ADMIN_KEY" \
     -H "Content-Type: application/json" \
     -d '{
       "application_id": "YOUR_APPLICATION_UUID",
       "name": "Production Alerts Bot",
       "bot_token": "7123456789:AAH...",
       "default_chat_id": "-100123456789"
     }'
   ```
4. Test the bot configuration:
   ```bash
   curl -X POST "http://localhost:8000/api/v1/admin/telegram/{config_id}/test?chat_id=YOUR_CHAT_ID" \
     -H "X-Admin-API-Key: YOUR_ADMIN_KEY"
   ```

### 2. Gmail / Email Integration (Google App Password)
Non è necessario configurare OAuth 2.0 complessi o Cloud Console redirect: puoi utilizzare direttamente la **Password per le applicazioni** di Google via SMTP sicuro (`smtp.gmail.com:587` con STARTTLS).

#### Come generare la Password per le applicazioni su Google:
1. Accedi al tuo account Google e vai su **[Gestisci il tuo account Google](https://myaccount.google.com/)**.
2. Nel menu a sinistra seleziona **Sicurezza**.
3. Sotto "Modalità di accesso a Google", assicurati che la **Verifica in due passaggi** sia attiva.
4. Cerca nella barra in alto **"Password per le app"** (o vai su `https://myaccount.google.com/apppasswords`).
5. Dai un nome all'app (es. `Notification Gateway`) e clicca su **Crea**.
6. Google mostrerà una password di **16 caratteri** (es. `abcd efgh ijkl mnop`).
7. Inserisci la password nel tuo file `.env`:
   ```ini
   SMTP_HOST="smtp.gmail.com"
   SMTP_PORT=587
   SMTP_USER="tuaemail@gmail.com"
   SMTP_PASSWORD="abcd efgh ijkl mnop"
   TEST_EMAIL_RECIPIENT="tuaemail@gmail.com"
   ```
8. Registra la configurazione nel Gateway via API:
   ```bash
   curl -X POST http://localhost:8080/api/v1/admin/gmail \
     -H "X-Admin-API-Key: YOUR_ADMIN_KEY" \
     -H "Content-Type: application/json" \
     -d '{
       "application_id": "YOUR_APPLICATION_UUID",
       "name": "Gmail Aziendale",
       "email_address": "tuaemail@gmail.com",
       "auth_type": "app_password",
       "app_password": "abcd efgh ijkl mnop",
       "smtp_host": "smtp.gmail.com",
       "smtp_port": 587
     }'
   ```
9. La password verrà **cifrata a riposo con AES-256-GCM** e non sarà mai mostrata in chiaro.

---

## 💻 Integration Examples

### cURL

#### Send a Telegram Notification
```bash
curl -X POST http://localhost:8000/api/v1/notifications/telegram \
  -H "X-API-Key: ng_live_xxxx_yyyy" \
  -H "X-Idempotency-Key: tx_unique_order_1001" \
  -H "Content-Type: application/json" \
  -d '{
    "configuration_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "chat_id": "123456789",
    "message": "<b>Order Confirmed!</b>\nOrder #1001 was processed successfully.",
    "parse_mode": "HTML",
    "buttons": [
      [
        {"text": "Track Order", "url": "https://example.com/orders/1001"}
      ]
    ]
  }'
```

#### Send an Email via Gmail API
```bash
curl -X POST http://localhost:8000/api/v1/notifications/email \
  -H "X-API-Key: ng_live_xxxx_yyyy" \
  -H "X-Idempotency-Key: email_inv_1001" \
  -H "Content-Type: application/json" \
  -d '{
    "configuration_id": "2fa85f64-5717-4562-b3fc-2c963f66afa5",
    "to": ["customer@example.com"],
    "subject": "Invoice for Order #1001",
    "text": "Thank you for your business. Find your invoice attached.",
    "html": "<h3>Thank you!</h3><p>Your order has been shipped.</p>",
    "attachments": [
      {
        "filename": "invoice_1001.pdf",
        "content_base64": "JVBERi0xLjQKJ...",
        "content_type": "application/pdf"
      }
    ]
  }'
```

#### Check Notification Delivery Status
```bash
curl -X GET http://localhost:8000/api/v1/notifications/{notification_id} \
  -H "X-API-Key: ng_live_xxxx_yyyy"
```

---

### Python Integration

```python
import httpx

class NotificationGatewayClient:
    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url.rstrip("/")
        self.headers = {
            "X-API-Key": api_key,
            "Content-Type": "application/json",
        }

    def send_telegram(self, configuration_id: str, chat_id: str, message: str, idempotency_key: str = None):
        headers = dict(self.headers)
        if idempotency_key:
            headers["X-Idempotency-Key"] = idempotency_key

        payload = {
            "configuration_id": configuration_id,
            "chat_id": chat_id,
            "message": message,
            "parse_mode": "HTML",
        }
        response = httpx.post(f"{self.base_url}/api/v1/notifications/telegram", json=payload, headers=headers)
        response.raise_for_status()
        return response.json()

    def send_email(self, configuration_id: str, to: list[str], subject: str, html: str, idempotency_key: str = None):
        headers = dict(self.headers)
        if idempotency_key:
            headers["X-Idempotency-Key"] = idempotency_key

        payload = {
            "configuration_id": configuration_id,
            "to": to,
            "subject": subject,
            "html": html,
        }
        response = httpx.post(f"{self.base_url}/api/v1/notifications/email", json=payload, headers=headers)
        response.raise_for_status()
        return response.json()

# Usage:
client = NotificationGatewayClient("http://localhost:8000", "ng_live_xxxx_yyyy")
result = client.send_telegram(
    configuration_id="config-uuid",
    chat_id="123456789",
    message="System health: <b>NORMAL</b>",
    idempotency_key="daily_report_20261109"
)
print("Dispatched:", result["data"]["status"])
```

---

### JavaScript / Node.js Integration

```javascript
async function sendNotification({ configurationId, chatId, message, idempotencyKey, apiKey }) {
  const response = await fetch("http://localhost:8000/api/v1/notifications/telegram", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-API-Key": apiKey,
      ...(idempotencyKey ? { "X-Idempotency-Key": idempotencyKey } : {}),
    },
    body: JSON.stringify({
      configuration_id: configurationId,
      chat_id: chatId,
      message: message,
      parse_mode: "HTML",
    }),
  });

  if (!response.ok) {
    const errorBody = await response.json();
    throw new Error(`Notification failed: ${JSON.stringify(errorBody)}`);
  }

  const result = await response.json();
  return result.data;
}

// Usage
sendNotification({
  configurationId: "your-config-uuid",
  chatId: "123456789",
  message: "🚀 Deployment finished successfully!",
  idempotencyKey: "deploy_v1.0.4",
  apiKey: "ng_live_xxxx_yyyy",
}).then(data => console.log("Delivered notification ID:", data.id));
```

---

## ⚙️ Environment Variables Reference

| Variable | Description | Default |
|---|---|---|
| `DATABASE_URL` | SQLAlchemy async connection string (PostgreSQL or SQLite) | `sqlite+aiosqlite:///./notification_gateway.db` |
| `REDIS_URL` | Redis instance connection URI | `None` |
| `REDIS_ENABLED` | Enable Redis for rate limiting (fallback to in-memory sliding window) | `false` |
| `MASTER_ENCRYPTION_KEY` | 32-byte URL-safe base64 key for AES-256-GCM encryption | **Required** |
| `ACTIVE_KEY_VERSION` | Current encryption key version identifier | `v1` |
| `KEY_ROTATION_RING` | JSON string of versioned keys for rotation | `{}` |
| `API_KEY_PEPPER` | Secret pepper used in HMAC-SHA256 API key hashing | **Required** |
| `ADMIN_API_KEY` | Bootstrap admin key for `/api/v1/admin/*` endpoints | **Required** |
| `DEFAULT_RATE_LIMIT_PER_MINUTE` | Default rate limit applied to client applications | `60` |
| `NOTIFICATION_MAX_RETRIES` | Max retry attempts for transient provider failures | `3` |
| `NOTIFICATION_RETRY_BACKOFF_FACTOR` | Exponential backoff factor (delay = factor^(attempt-1) + jitter) | `1.5` |
| `NOTIFICATION_TIMEOUT_SECONDS` | HTTP timeout when contacting external providers | `15.0` |
| `MAX_ATTACHMENT_SIZE_BYTES` | Maximum email attachment size in bytes | `10485760` (10 MB) |
| `CORS_ORIGINS` | Allowed CORS origins (JSON array or comma-separated) | `["*"]` |
| `GOOGLE_OAUTH_REDIRECT_URI` | Authorized OAuth redirect callback URL | `http://localhost:8000/api/v1/admin/gmail/oauth/callback` |

---

## 🧪 Testing

The test suite covers unit tests for encryption, security, and providers, alongside integration tests for API endpoints, idempotency, retries, and multi-tenant isolation.

Run all tests:
```bash
pytest -v
```

Run tests with coverage report:
```bash
pytest --cov=app --cov-report=term-missing
```

---

## 📄 License
MIT License. Created by Senior Backend Engineer.

