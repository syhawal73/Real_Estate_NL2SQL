# 🏠 Real Estate Chatbot — AI-Powered Property Discovery Platform

A full-stack, conversational real-estate assistant that lets users discover and explore properties through natural language. The chatbot translates human queries into SQL (NL2SQL), executes them against a live property database, and presents results as rich property cards — all within a modern React UI.

> **LLM-Provider Agnostic** — swap between LM Studio, Ollama, OpenAI, Anthropic, or Gemini without changing a single line of application code.

---

## ✨ Features

### Conversational AI
- **Natural-language property search** — ask for properties the way you'd ask a friend ("3-bedroom apartments under $500K in Dubai")
- **Multi-turn conversations** — refine, modify, or start new searches across chat turns with full context preservation
- **Smart clarification** — the bot asks follow-up questions only when the information is necessary or materially useful
- **Zero-result fallback** — automatically relaxes constraints one at a time when no exact matches are found, and reports what was relaxed
- **General real-estate chat** — answers real-estate questions; politely redirects unrelated topics

### Deterministic Pipeline
- **NL2SQL agent** built with [LangGraph](https://github.com/langchain-ai/langgraph) — a multi-node state graph that routes, extracts, plans, queries, and responds
- **Deterministic where possible** — property extraction, action routing, query planning, SQL generation, and card data use rule-based logic; the LLM is only used for natural-language presentation
- **Count, aggregation & comparison** — "How many villas are in Sharjah?", "Compare these two properties" — handled deterministically

### Full-Stack Application
- **Rich property cards** — up to 5 cards per response, each linking to a canonical property detail page
- **"View all" overflow** — result sets larger than 5 expose a link preserving active filters
- **User authentication** — cookie-based auth with registration, login, email verification, and password reset flows
- **Admin dashboard** — manage users and hot-swap LLM provider/model settings at runtime
- **Responsive UI** — mobile-friendly React + Tailwind CSS interface

---

## 🏗️ Architecture

```
┌───────────────────────────────────────────────────────────────────────┐
│                         Docker Compose                                │
│                                                                       │
│  ┌───────────── ┐    ┌──────────────────┐    ┌─────────────────────┐  │
│  │  Frontend    │    │     Backend      │    │    PostgreSQL 16    │  │
│  │  React/Vite  │───▶   FastAPI +       ───▶│                     │  │
│  │  :5173       │    │   LangGraph      │    │    :5432            │  │
│  └───────────── ┘    │   :8000          │    └─────────────────────┘  │
│                      │                  │                 ▲           │
│                      └────────┬─────────┘                 │           │
│                               │              ┌────────────┘           │
│                               │              │  DB Seed               │
│                               │              │  (runs once)           │
│                               │              └──────────────────── ┐  │
└───────────────────────────────┼────────────────────────────────────┘  │
                                │                                       │
                                ▼                                       │
                       ┌──────────────── ┐                              │
                       │   LLM Server    │                              │
                       │  (Host Machine) │                              │
                       │  LM Studio /    │                              │
                       │  Ollama / API   │                              │
                       └──────────────── ┘                              │
```

### LangGraph Agent Pipeline

The chatbot's core is a **LangGraph state graph** with the following node sequence:

```
START
  │
  ▼
load_memory ──▶ level1_extraction ──▶ classify_action
                                           │
                    ┌──────────────────────┼──────────────────────┐
                    ▼                      ▼                      ▼
           reset_search_context   modify_search_context   extract_constraints
                    │                      │                      │
                    └──────────┬───────────┘──────────────────────┘
                               ▼
                      needs_clarification
                         │           │
                  (yes)  │           │  (no)
                         ▼           ▼
                  level4_response  level3_query_planner
                         │           │
                         │           ▼
                         │     execute_query
                         │           │
                         └─────┬─────┘
                               ▼
                        level4_response ──▶ update_memory ──▶ END
```

| Node | Role |
|------|------|
| `load_memory` | Retrieves conversation history and active search context |
| `level1_extraction` | Deterministic entity extraction (city, neighbourhood, price, bedrooms, intent, etc.) |
| `classify_action` | Routes to new search, modify search, general chat, or property refinement |
| `extract_constraints` | Builds structured search constraints from entities |
| `needs_clarification` | Decides if a follow-up question is needed before querying |
| `level3_query_planner` | Deterministic SQL query planning from search constraints |
| `execute_query` | Runs the generated SQL against PostgreSQL with zero-result fallback |
| `level4_response` | LLM-powered natural-language response generation with property card payloads |
| `update_memory` | Persists conversation state and search context |

---

## 🛠️ Tech Stack

### Backend
| Technology | Purpose |
|-----------|---------|
| **Python 3.12** | Runtime |
| **FastAPI** | REST API framework |
| **LangGraph** | Agent orchestration (state graph) |
| **LangChain Core** | LLM abstractions |
| **SQLAlchemy 2.0** (async) | ORM & database toolkit |
| **asyncpg** | Async PostgreSQL driver |
| **Pydantic v2** | Data validation & settings |
| **Poetry** | Dependency management |

### Frontend
| Technology | Purpose |
|-----------|---------|
| **React 18** | UI framework |
| **TypeScript** | Type safety |
| **Vite 5** | Build tool & dev server |
| **Tailwind CSS 3** | Utility-first styling |
| **React Router 6** | Client-side routing |
| **Axios** | HTTP client |
| **Radix UI** | Accessible primitives |
| **Lucide React** | Icons |

### Infrastructure
| Technology | Purpose |
|-----------|---------|
| **Docker & Docker Compose** | Containerised deployment |
| **PostgreSQL 16** | Relational database |
| **LM Studio / Ollama / OpenAI / Anthropic / Gemini** | LLM provider (pluggable) |

---

## 📁 Project Structure

```
Real_Estate/
├── docker-compose.yml          # Unified compose — all services
│
├── backend/
│   ├── Dockerfile
│   ├── pyproject.toml           # Poetry dependencies
│   ├── .env.example             # Environment variable reference
│   └── app/
│       ├── main.py              # FastAPI app + lifespan
│       ├── config/
│       │   └── settings.py      # Pydantic settings (env vars)
│       ├── agents/
│       │   └── free_chat/       # LangGraph NL2SQL agent
│       │       ├── graph.py     # State graph definition
│       │       ├── state.py     # AgentState TypedDict
│       │       ├── prompts.py   # LLM prompt templates
│       │       ├── deterministic_builder.py
│       │       ├── utils.py
│       │       └── nodes/       # 11 graph nodes
│       │           ├── load_memory.py
│       │           ├── level1_extraction.py
│       │           ├── classify_action.py
│       │           ├── extract_constraints.py
│       │           ├── modify_search_context.py
│       │           ├── reset_search_context.py
│       │           ├── needs_clarification.py
│       │           ├── level3_query_planner.py
│       │           ├── execute_query.py
│       │           ├── level4_response.py
│       │           └── update_memory.py
│       ├── api/
│       │   ├── dependencies.py
│       │   └── routes/
│       │       ├── free_chat.py   # POST /api/chat
│       │       ├── auth.py        # Registration, login, password reset
│       │       ├── account.py     # User account management
│       │       ├── admin.py       # Admin dashboard API
│       │       ├── properties.py  # Property CRUD & search
│       │       ├── metadata.py    # Cities, neighbourhoods
│       │       ├── stats.py       # Platform statistics
│       │       └── health.py      # Health check
│       ├── domain/
│       │   ├── property/          # Property models, schemas, repo, service
│       │   ├── chat/              # Chat session models, schemas, repo, service
│       │   ├── auth/              # User auth models, schemas, service
│       │   └── admin/             # Admin settings models
│       ├── conversation/          # Action classifier, modify/new search, clarification
│       └── infrastructure/
│           ├── database/          # Async engine, session factory
│           ├── llm/               # LLM provider abstraction
│           │   ├── base.py        # LLMProvider ABC
│           │   ├── factory.py     # Provider factory (hot-swappable)
│           │   └── providers/
│           │       ├── openai_compatible.py  # OpenAI, LM Studio, Ollama, Gemini
│           │       └── anthropic_provider.py # Anthropic Claude
│           ├── email/             # SMTP email service
│           └── security/          # Password hashing
│
├── frontend/
│   ├── Dockerfile
│   ├── package.json
│   ├── vite.config.ts
│   ├── tailwind.config.cjs
│   └── src/
│       ├── App.tsx               # Routes & layout
│       ├── main.tsx              # React entrypoint
│       ├── types.ts              # Shared TypeScript types
│       ├── auth/
│       │   └── AuthContext.tsx    # Auth state provider
│       ├── components/
│       │   ├── PropertyCard.tsx   # Rich property result card
│       │   ├── ProtectedRoute.tsx # Auth guard (user & admin)
│       │   ├── layout/           # Navbar, Footer
│       │   └── ui/               # Reusable UI primitives
│       ├── pages/
│       │   ├── Home.tsx
│       │   ├── Listings.tsx
│       │   ├── PropertyDetail.tsx
│       │   ├── FreeChatPreview.tsx  # Chat interface
│       │   ├── WorkflowPreview.tsx
│       │   ├── Login.tsx
│       │   ├── Register.tsx
│       │   ├── ForgotPassword.tsx
│       │   ├── ResetPassword.tsx
│       │   └── admin/
│       │       └── AdminDashboard.tsx
│       ├── services/
│       │   └── api.ts            # Axios API client
│       └── lib/                  # Utility helpers
│
├── db_seed/
│   ├── Dockerfile
│   ├── seed.py                   # CSV → PostgreSQL upsert seeder
│   ├── city_centers.csv          # City coordinate data
│   ├── properties.csv            # Property inventory (~70K)
│   └── migrations/
│       └── 001_auth_admin.sql    # Auth/admin schema migration
│
├── scripts/
│   ├── setup.sh                  # First-time build & start
│   ├── run.sh                    # Subsequent starts
│   ├── stop.sh                   # Stop (with optional --clean)
│   └── logs.sh                   # View container logs
│
├── tests/
│   └── test_chat.py              # Integration tests
│
└── docs/
    ├── CHATBOT_REQUIREMENTS.md   # Product contract
    ├── IMPLEMENTATION_NOTES.md   # Implementation details
    ├── TESTING_STATUS.md         # Test coverage status
    └── langraph_overview.md      # LangGraph reference
```

---

## 🚀 Getting Started

### Prerequisites

| Requirement | Notes |
|------------|-------|
| **Docker Desktop** | Includes Docker Compose v2. This is the **only** prerequisite — Python, Node.js, and PostgreSQL all run inside containers. |
| **LLM Server** | [LM Studio](https://lmstudio.ai/), [Ollama](https://ollama.ai/), or a cloud API key (OpenAI / Anthropic / Gemini). Must be running on the host machine at the configured port. |

### First-Time Setup

```bash
# 1. Clone the repository
git clone <repo-url>
cd Real_Estate

# 2. Make scripts executable (Git Bash / WSL / Linux / macOS)
chmod +x scripts/*.sh

# 3. Run the first-time setup (builds images, starts containers, seeds DB)
bash scripts/setup.sh
```

The setup script will:
1. ✅ Verify Docker & Docker Compose are installed
2. ✅ Build all Docker images from scratch (`--no-cache`)
3. ✅ Start all containers in detached mode
4. ✅ Wait for PostgreSQL healthcheck to pass
5. ✅ Wait for the Backend API to respond at `/health`
6. ✅ Print access URLs

### Subsequent Runs

```bash
# Start all services
bash scripts/run.sh

# Start and follow logs
bash scripts/run.sh --logs

# Rebuild images (after Dockerfile/dependency changes) then start
bash scripts/run.sh --build
```

### Stop

```bash
# Stop containers (database data is preserved)
bash scripts/stop.sh

# Stop and DELETE all data (database volume removed)
bash scripts/stop.sh --clean
```

### View Logs

```bash
bash scripts/logs.sh                # All services
bash scripts/logs.sh backend        # Backend only
bash scripts/logs.sh frontend       # Frontend only
bash scripts/logs.sh postgres       # Database only
```

---

## 🌐 Access URLs

| Service | URL |
|---------|-----|
| **Frontend** | [http://localhost:5173](http://localhost:5173) |
| **Backend API** | [http://localhost:8000](http://localhost:8000) |
| **Swagger Docs** | [http://localhost:8000/docs](http://localhost:8000/docs) |
| **ReDoc** | [http://localhost:8000/redoc](http://localhost:8000/redoc) |

---

## ⚙️ Configuration

### Environment Variables

Copy the example and customise:

```bash
cp backend/.env.example backend/.env
```

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `postgresql+asyncpg://...` | PostgreSQL connection string (auto-promoted to asyncpg) |
| `DB_ECHO` | `false` | Log all SQL statements |
| `LLM_PROVIDER` | `lmstudio` | `ollama` · `lmstudio` · `openai` · `anthropic` · `gemini` |
| `LLM_MODEL` | `google/gemma-3-4b` | Model identifier for the chosen provider |
| `LLM_BASE_URL` | `http://localhost:1234/v1` | API base URL (not used for Anthropic) |
| `LLM_API_KEY` | `lm-studio` | API key or token |
| `LLM_TEMPERATURE` | `0.1` | Response temperature |
| `LLM_MAX_TOKENS` | `1024` | Max tokens per response |
| `ADMIN_EMAIL` | `admin@example.com` | Auto-created admin account email |
| `ADMIN_PASSWORD` | `ChangeMe_12345!` | Auto-created admin account password |
| `FRONTEND_URL` | `http://localhost:5173` | CORS origin for the frontend |

> [!IMPORTANT]
> When running via Docker Compose, the environment variables defined in `docker-compose.yml` **override** the backend `.env` file. Edit the compose file for Docker-based configuration changes.

### Switching LLM Providers

Simply change `LLM_PROVIDER`, `LLM_MODEL`, `LLM_BASE_URL`, and `LLM_API_KEY`:

```bash
# Ollama (local)
LLM_PROVIDER=ollama
LLM_MODEL=qwen2.5-coder:3b-instruct-q6_K
LLM_BASE_URL=http://localhost:11434/v1
LLM_API_KEY=ollama

# OpenAI (cloud)
LLM_PROVIDER=openai
LLM_MODEL=gpt-4o-mini
LLM_BASE_URL=https://api.openai.com/v1
LLM_API_KEY=sk-...

# Anthropic (cloud)
LLM_PROVIDER=anthropic
LLM_MODEL=claude-sonnet-4-20250514
LLM_API_KEY=sk-ant-...
```

LLM settings can also be hot-swapped at runtime via the **Admin Dashboard** (`/admin`) without restarting the backend.

---

## 🗄️ Database

- **Engine**: PostgreSQL 16 (Alpine)
- **Seeder**: The `db_seed` container runs once on first startup, upserting data from `city_centers.csv` and `properties.csv` using `ON CONFLICT ... DO UPDATE` (safe to re-run)
- **Persistence**: Data is stored in a named Docker volume (`re_chatbot_postgres_data`). Survives `docker compose down`; destroyed with `docker compose down -v` or `scripts/stop.sh --clean`
- **Schema**: Tables are auto-created on backend startup via SQLAlchemy `Base.metadata.create_all`

### Property Schema

| Column | Type | Description |
|--------|------|-------------|
| `id` | `INTEGER` (PK) | Unique property ID |
| `title` | `VARCHAR` | Property title |
| `city` | `VARCHAR` | City name |
| `neighbourhood` | `VARCHAR` | Neighbourhood name |
| `intent` | `VARCHAR` | `rent` or `buy` |
| `price` | `INTEGER` | Price in local currency |
| `bedrooms` | `INTEGER` | Number of bedrooms |
| `bathrooms` | `INTEGER` | Number of bathrooms |
| `size_sqm` | `INTEGER` | Size in square metres |
| `property_type` | `VARCHAR` | `apartment` or `house` |
| `distance_from_city_km` | `DOUBLE PRECISION` | Distance from city centre |
| `description` | `TEXT` | Full property description |

---

## 🔒 Authentication

- **Cookie-based session auth** — HTTP-only, configurable `SameSite` and `Secure` flags
- **Flows**: Registration → Email verification → Login → Password reset
- **Roles**: `USER` (default) and `ADMIN`
- **Admin auto-seed**: An admin account is created on first startup from `ADMIN_EMAIL` / `ADMIN_PASSWORD`
- **Protected routes**: `/chat` requires authentication; `/admin` requires the `ADMIN` role

> [!NOTE]
> In development, when SMTP is not configured, email verification and password-reset URLs are logged to the console instead of being sent via email.

Admin Login Credentials:
Email:    admin@example.com
Password: ChangeMe_12345!
Role:     ADMIN
http://localhost:5173/login?next=%2Fadmin
---

## 🧪 Testing

```bash
# Run backend tests (from within the backend container or with Poetry env active)
cd backend
poetry run pytest

# Run with coverage
poetry run pytest --cov=app

# Skip tests that require a running LLM
poetry run pytest -m "not llm"
```

---

## 📝 API Endpoints

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| `GET` | `/health` | — | Health check |
| `POST` | `/api/chat` | ✅ | Send a chat message, receive AI response + property cards |
| `GET` | `/api/properties` | — | Search/list properties with filters |
| `GET` | `/api/properties/{id}` | — | Get a single property by ID |
| `GET` | `/api/metadata/cities` | — | List all cities |
| `GET` | `/api/metadata/neighbourhoods` | — | List neighbourhoods (filterable by city) |
| `GET` | `/api/stats` | — | Platform statistics |
| `POST` | `/api/auth/register` | — | Register a new user |
| `POST` | `/api/auth/login` | — | Log in (sets session cookie) |
| `POST` | `/api/auth/logout` | ✅ | Log out (clears cookie) |
| `GET` | `/api/account/me` | ✅ | Get current user profile |
| `GET/PUT` | `/api/admin/*` | 🔐 | Admin-only management endpoints |

---

## 🗺️ Frontend Routes

| Path | Component | Auth | Description |
|------|-----------|------|-------------|
| `/` | `Home` | — | Landing page with hero, stats, and search |
| `/properties` | `Listings` | — | Property listings with filters |
| `/properties/:id` | `PropertyDetail` | — | Individual property page |
| `/chat` | `FreeChatPreview` | ✅ | AI chat interface |
| `/workflow` | `WorkflowPreview` | — | Agent workflow visualisation |
| `/login` | `Login` | — | Login form |
| `/register` | `Register` | — | Registration form |
| `/forgot-password` | `ForgotPassword` | — | Password reset request |
| `/reset-password` | `ResetPassword` | — | Password reset form |
| `/admin` | `AdminDashboard` | 🔐 | Admin panel |

---

## 📄 License

This project is for personal/educational use. See the repository for license details.
