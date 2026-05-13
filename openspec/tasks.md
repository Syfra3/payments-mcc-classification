# SDD Tasks: payments-mcc-classification

**Change**: payments-mcc-classification  
**Status**: Ready for Implementation  
**Total Tasks**: 47  
**Execution Model**: Sequential phases with intra-phase parallelization where noted  
**Artifact Store**: openspec

---

## Executive Summary

Decomposition of Python/FastAPI merchant classification microservice into 47 atomic, testable tasks organized across 13 sequential phases. The service implements a full domain model (9 entities), 19 API endpoints, pluggable provider abstraction (LLM + card processors), and a pipeline engine framework with transactional outbox event delivery.

**Work can proceed in 5 phases that may partially overlap**:
1. **Project Bootstrap** (4 tasks) — must complete first
2. **Core Infrastructure** (5 tasks) — may start when Bootstrap done
3. **Data Layer** (7 tasks) — may parallelize after Infrastructure
4. **Engine & Providers** (9 tasks) — may start after Core complete
5. **API & Workers** (16 tasks) — may parallelize substantially after Engine complete
6. **Tests & Finalization** (6 tasks) — must complete after all feature code

---

## Execution Guidance

### Phase Dependencies (DAG)
```
Bootstrap → Infrastructure → Data Layer ↘
                                       ├→ Engine & Providers ↘
                                                             ├→ API & Workers ↘
                                                                               ├→ Tests
```

### Parallelization Opportunities
- **Data Layer** (7 tasks): Models + migrations + repositories can parallelize after Data Layer design task
- **Engine & Providers** (9 tasks): LLM provider + Card provider + Pipeline engine can run in parallel after framework foundation
- **API & Workers** (16 tasks): Routers can parallelize; Worker can run independently after Infrastructure/Data complete
- **Tests** (6 tasks): Unit tests can parallelize; integration/e2e depend on all feature code

### Review Workload Forecast

**Estimated Changed Lines**: 8,500–10,000  
- Models + migrations: ~1,200  
- Services (core + pipeline steps): ~2,500  
- Repositories + schemas: ~1,800  
- API routes (19 endpoints): ~2,000  
- Providers (LLM + Card): ~1,500  
- Tests (unit + integration + e2e): ~2,000  
- Infrastructure (config, context, workers): ~800  
- Docker, pyproject, README: ~500  

**Chained PRs Recommended**: **YES**  
- Phase 1 (Bootstrap): Standalone, no code.
- Phase 2 (Infrastructure): Isolated config/context, safe to merge.
- Phase 3 (Data Layer): Models/migrations, safe to merge, tests can depend on it.
- Phase 4 (Engine & Providers): Core logic layer, high-value, can land independently.
- Phase 5 (API & Workers): Feature endpoints, can merge in slices (Merchant → MCC → External → Worker).
- Phase 6 (Tests & Finalization): Validation only, no risk.

**Single-PR Strategy NOT RECOMMENDED** — total size ~10K lines exceeds maintainability threshold; chained PRs provide reviewability, risk isolation, and continuous team feedback.

**Decision Needed Before Apply**: 
- Confirm Python version pin (3.11 vs 3.12)
- Confirm PostgreSQL version & pgvector extension requirement
- Confirm LangFuse tracing requirement (optional vs mandatory)
- Confirm whether Docker dev environment mandatory or optional

---

## Phase 1: Project Bootstrap (4 tasks)

*Tasks are **sequential** — each depends on prior completion. No parallelization.*

### Task 1.1: Initialize Repository Structure
**Spec Requirement**: Support all 9 capabilities via organized module structure  
**Depends On**: None  
**Delivery**: Directory tree + stub files  
**Verification**:
```bash
ls -la payments-mcc-classification/
# Verify: app/, alembic/, tests/, docker-compose.yml, pyproject.toml, .env.example, README.md exist
```

**Details**:
- Create `payments-mcc-classification/` root directory
- Create subdirectories:
  - `app/` (main package)
  - `app/api/v1/` (routers)
  - `app/services/` (business logic)
  - `app/pipeline/` (engine + steps)
  - `app/providers/` (LLM + Card abstractions)
  - `app/repositories/` (data access)
  - `app/models/` (SQLAlchemy entities)
  - `app/core/` (config, context, exceptions, auth)
  - `app/workers/` (Outbox processor)
  - `app/schemas/` (Pydantic v2)
  - `tests/unit/`, `tests/integration/`, `tests/e2e/`
  - `alembic/versions/`
- Create stub `__init__.py` files in all packages
- Create `main.py` (FastAPI app factory)

---

### Task 1.2: Configure pyproject.toml
**Spec Requirement**: Runtime + dev dependencies for FastAPI, SQLAlchemy, pgvector, LangChain, pytest, etc.  
**Depends On**: Task 1.1  
**Delivery**: pyproject.toml with all dependencies pinned  
**Verification**:
```bash
cd payments-mcc-classification && python -m pip install -e ".[dev]" --dry-run
# Should list 25+ packages without conflicts
```

**Details**:
- Python version: `python = ">=3.11,<4"`
- Core dependencies:
  - fastapi ^0.104
  - sqlalchemy[asyncio] ^2.0
  - asyncpg ^0.29
  - alembic ^1.13
  - pydantic-settings ^2.1
  - pydantic[email] ^2.5
  - pgvector ^0.2
  - httpx ^0.25
  - langchain ^0.1
  - langfuse ^2.0 (optional)
  - openai ^1.3
  - python-dotenv ^1.0
  - structlog ^24.1
- Dev dependencies:
  - pytest ^7.4
  - pytest-asyncio ^0.21
  - pytest-cov ^4.1
  - black ^23.12
  - ruff ^0.1
  - mypy ^1.7
  - httpx (for mock client)
- Scripts section:
  - `dev`: uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
  - `lint`: ruff check . && mypy . && black --check .
  - `format`: black . && ruff check . --fix
  - `test`: pytest
  - `test:cov`: pytest --cov=app --cov-report=html
  - `migrate`: alembic upgrade head
  - `migrate:create`: alembic revision --autogenerate -m

---

### Task 1.3: Create .env.example and docker-compose.yml
**Spec Requirement**: Local development environment, PostgreSQL + pgvector extension  
**Depends On**: Task 1.1  
**Delivery**: Two files with all env vars + service config  
**Verification**:
```bash
docker-compose up -d
sleep 3 && docker-compose exec postgres psql -U postgres -c "CREATE EXTENSION IF NOT EXISTS vector;"
docker-compose down
# Should succeed without errors
```

**Details**:

**`.env.example`**:
```
ENVIRONMENT=development
LOG_LEVEL=DEBUG
DATABASE_URL=postgresql+asyncpg://postgres:password@localhost:5432/merchant_db
OPENAI_API_KEY=sk-...
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
POMELO_API_KEY=...
POMELO_BASE_URL=https://api.pomelo.dev
TAVILY_API_KEY=...
LANGFUSE_PUBLIC_KEY=...
LANGFUSE_SECRET_KEY=...
PORT_HTTP=8000
CORS_ORIGINS=http://localhost:3000,http://localhost:8000
HMAC_SECRET=your-shared-secret
MAX_WORKERS=4
```

**`docker-compose.yml`**:
- Service: `postgres:16-alpine` with pgvector extension
- Environment: POSTGRES_DB=merchant_db, POSTGRES_PASSWORD=password, POSTGRES_USER=postgres
- Volume: `postgres_data:/var/lib/postgresql/data`
- Health check: pg_isready on port 5432
- Port mapping: 5432:5432
- Service: `redis:7-alpine` (optional, for distributed locking)
- Override `.env` from `.env.example` with local values

---

### Task 1.4: Initialize Alembic for Migrations
**Spec Requirement**: Database versioning and schema management  
**Depends On**: Task 1.1  
**Delivery**: alembic/ directory with env.py, script.py.mako, .env integration  
**Verification**:
```bash
cd payments-mcc-classification
alembic revision --autogenerate -m "initial schema"
# Should create alembic/versions/*.py without errors
```

**Details**:
- Run `alembic init -t async alembic` (async template)
- Configure `alembic/env.py`:
  - Load DATABASE_URL from `.env` via python-dotenv
  - Import all SQLAlchemy models (to discover schema for auto-generate)
  - Set `target_metadata = Base.metadata`
  - Enable sqlalchemy.url fallback
- Configure `alembic.ini`:
  - sqlalchemy.url = (commented, use env var instead)
  - script_location = alembic
  - version_path_separator = :
  - file_template = %%(rev)s_%%(slug)s
- Create stub migration: `alembic/versions/001_initial_schema.py`

---

## Phase 2: Core Infrastructure (5 tasks)

*Tasks can proceed **in parallel** after Phase 1 complete. They have no inter-dependencies.*

### Task 2.1: Implement Config & Settings
**Spec Requirement**: Env var validation, type-safe configuration for all 9 capabilities  
**Depends On**: Task 1.2, 1.3  
**Delivery**: `app/core/config.py` with Pydantic Settings  
**Verification**:
```bash
cd payments-mcc-classification && python -c "from app.core.config import settings; print(settings.database_url, settings.environment)"
# Should load from .env without error
```

**Details**:
- Class `Settings(BaseSettings)`:
  - Model config: ConfigDict(env_file=".env", case_sensitive=False)
  - Fields:
    - environment: Literal["development", "staging", "production"]
    - log_level: str = "INFO"
    - database_url: str (validate format postgresql+asyncpg://...)
    - port_http: int = 8000
    - openai_api_key: str
    - openai_embedding_model: str = "text-embedding-3-small"
    - openai_embedding_dims: int = 1536
    - pomelo_api_key: str
    - pomelo_base_url: str
    - tavily_api_key: str (optional)
    - langfuse_public_key: str (optional)
    - langfuse_secret_key: str (optional)
    - cors_origins: list[str]
    - hmac_secret: str
    - max_workers: int = 4
    - log_requests: bool = True
  - Validators:
    - @field_validator('database_url') → ensure starts with "postgresql+asyncpg://"
    - @field_validator('environment') → accept only valid envs
  - Singleton: `settings = Settings()`

---

### Task 2.2: Implement Context Manager (ContextVar[AsyncSession])
**Spec Requirement**: Transaction management via contextvars (TM capability 7)  
**Depends On**: Task 1.2  
**Delivery**: `app/core/context.py` with ContextVar + @transactional decorator  
**Verification**:
```bash
cd payments-mcc-classification && python -c "from app.core.context import transactional_context; print(transactional_context.get())"
# Should print None (no ambient session)
```

**Details**:
- Module `app/core/context.py`:
  - ContextVar `transactional_context: ContextVar[AsyncSession | None] = ContextVar("session", default=None)`
  - Async context manager `async_session_context(session: AsyncSession)`:
    - Takes AsyncSession as parameter
    - Sets token on entry
    - Yields nothing (just manages context)
    - Resets token on exit
  - Decorator `@transactional(force_new: bool = False)`:
    - If force_new=True, create new session from engine
    - Otherwise, check if ambient session exists (from context)
    - If exists and force_new=False, reuse (nested call)
    - If not exists, create new from engine
    - Wrap method call in try/except:
      - On exception: rollback and re-raise
      - On success: commit
    - Always reset context token on exit
    - Support both sync and async functions (check using inspect.iscoroutinefunction)
  - Helper `get_session() → AsyncSession | None`:
    - Returns `transactional_context.get()`
    - Used by repositories to pull ambient session

---

### Task 2.3: Implement Custom Exceptions & Error Handling
**Spec Requirement**: Consistent error responses for validation, auth, business logic failures  
**Depends On**: Task 1.2  
**Delivery**: `app/core/exceptions.py` + middleware + exception handlers  
**Verification**:
```bash
cd payments-mcc-classification && python -c "from app.core.exceptions import ResourceNotFound; raise ResourceNotFound('test')"
# Should raise exception with status_code=404
```

**Details**:
- Base class `AppException(Exception)`:
  - Fields: message, status_code, error_code
  - __str__ returns message
  - to_response() returns {"error": error_code, "message": message}
  - Default status_code = 500
- Subclasses:
  - `ResourceNotFound(status_code=404, error_code="RESOURCE_NOT_FOUND")`
  - `ValidationFailed(status_code=422, error_code="VALIDATION_FAILED")`
  - `AuthenticationFailed(status_code=401, error_code="AUTHENTICATION_FAILED")`
  - `AuthorizationFailed(status_code=403, error_code="AUTHORIZATION_FAILED")`
  - `ConflictError(status_code=409, error_code="CONFLICT")`
  - `IntegrationError(status_code=503, error_code="INTEGRATION_ERROR")`
- FastAPI exception handlers:
  - @app.exception_handler(AppException) → JSONResponse with 5xx status + body
  - @app.exception_handler(RequestValidationError) → JSONResponse 422 with field details
  - Global middleware @app.middleware("http") → logs request/response + captures unhandled exceptions
- Logging:
  - Use structlog.get_logger() in handlers
  - Log full traceback for 5xx, summary for 4xx
  - Include request_id, method, path, status in all logs

---

### Task 2.4: Implement HMAC Authentication Guard
**Spec Requirement**: Verify X-API-Signature header (FastAPI Merchant API capability 1)  
**Depends On**: Task 2.1, 2.3  
**Delivery**: `app/core/auth.py` with HMAC guard + JWT fallback  
**Verification**:
```bash
python -c "
from app.core.auth import verify_hmac_signature
import hmac, hashlib
msg = 'test'
secret = 'secret'
sig = hmac.new(secret.encode(), msg.encode(), hashlib.sha256).hexdigest()
result = verify_hmac_signature(msg, sig, secret)
print(f'Valid: {result}')
"
# Should print "Valid: True"
```

**Details**:
- Function `verify_hmac_signature(message: str, signature: str, secret: str) -> bool`:
  - Compute HMAC-SHA256(message, secret)
  - Compare to provided signature using constant-time comparison (hmac.compare_digest)
  - Return bool
- FastAPI dependency `verify_request_signature()`:
  - Extract `X-API-Signature` header
  - If missing, return 401 (Unauthorized)
  - Reconstruct request body (from request.body())
  - Call verify_hmac_signature()
  - If valid, allow; else return 401
  - Does NOT verify JWT (fallback for internal requests without HMAC)
- Decorator `@require_hmac_auth`:
  - Dependency: Depends(verify_request_signature)
  - Apply to protected endpoints
- Health check `/health` is unprotected
- Health check `/health/ready` is unprotected

---

### Task 2.5: Implement Database Engine & AsyncSession Factory
**Spec Requirement**: Async SQLAlchemy engine, session factory for transaction management  
**Depends On**: Task 2.1, 1.4  
**Delivery**: `app/core/database.py` with engine + async_session_local  
**Verification**:
```bash
cd payments-mcc-classification && python -c "
from app.core.database import engine, async_session_local
import asyncio
async def test():
    async with async_session_local() as session:
        result = await session.execute('SELECT 1')
        print(result.scalar())
asyncio.run(test())
"
# Should print 1
```

**Details**:
- Module `app/core/database.py`:
  - Function `get_engine(database_url: str)`:
    - create_async_engine(database_url, echo=False, pool_size=20, max_overflow=0)
    - Set future=True
    - Return engine
  - Function `get_async_session_local(engine)`:
    - sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    - Return sessionmaker instance
  - Global instances:
    - `engine = get_engine(settings.database_url)`
    - `async_session_local = get_async_session_local(engine)`
  - Async context manager `get_db_session() -> AsyncGenerator[AsyncSession, None]`:
    - Create session from async_session_local
    - Yield
    - Close on exit
  - Function `init_db()`:
    - Called at app startup
    - Create all tables: Base.metadata.create_all(bind=engine)
    - Alternative: run alembic upgrade head

---

## Phase 3: Data Layer (7 tasks)

*Tasks **1–2** are sequential. Tasks **3–7** can parallelize after task 2 completes.*

### Task 3.1: Design & Create SQLAlchemy Models (Base + Mixins)
**Spec Requirement**: Foundational ORM layer for 9 entities  
**Depends On**: Task 2.5, 1.4  
**Delivery**: `app/models/__init__.py` with Base, TimestampMixin, SoftDeleteMixin  
**Verification**:
```bash
cd payments-mcc-classification && python -c "from app.models import Base, Merchant; print(Merchant.__tablename__)"
# Should print "merchant"
```

**Details**:
- Module `app/models/__init__.py`:
  - Import sqlalchemy (Column, String, Integer, DateTime, Boolean, ForeignKey, etc.)
  - Mixin `TimestampMixin`:
    - created_at: DateTime with server_default=func.now()
    - updated_at: DateTime with server_default=func.now(), onupdate=func.now()
  - Mixin `SoftDeleteMixin`:
    - deleted_at: DateTime | None = None
    - hybrid_property is_deleted → returns deleted_at is not None
    - hybrid_property is_active → returns deleted_at is None
  - Base class `Base` (declarative_base):
    - __tablename__ auto-derived from class name (e.g., Merchant → "merchant")
    - type_annotation_map: {list: ARRAY, dict: JSON}
  - Import all entity models (will be defined in subsequent tasks)

---

### Task 3.2: Create Database Initialization & Migration Infrastructure
**Spec Requirement**: Alembic version control, initial schema generation  
**Depends On**: Task 3.1, 1.4  
**Delivery**: `alembic/versions/001_initial.py` (auto-generated stub)  
**Verification**:
```bash
cd payments-mcc-classification
alembic upgrade head
# Should create all tables without error
```

**Details**:
- File `alembic/env.py`:
  - Import Base from app.models
  - Set target_metadata = Base.metadata
  - Configure sqlalchemy.url from DATABASE_URL env var
  - Enable autogenerate in alembic.ini
- Run `alembic revision --autogenerate -m "initial schema"` (will be done in task 3.3 after models created)
- Version file structure:
  - up() function: runs create_table operations
  - down() function: runs drop_table operations
  - Use alembic operations (op.create_table, op.create_index, etc.) not raw SQL
- Alembic config updates:
  - Enable sqlalchemy.url from env var
  - Set compare_type=True for better migrations

---

### Task 3.3: Implement Merchant Model & Repository
**Spec Requirement**: Core entity for FastAPI Merchant API (capability 1)  
**Depends On**: Task 3.1  
**Delivery**: `app/models/merchant.py`, `app/repositories/merchant_repository.py`  
**Verification**:
```bash
cd payments-mcc-classification && python -c "
from app.models import Merchant
m = Merchant(name='TEST', provider='pomelo')
print(m.name, m.provider)
"
# Should print "TEST pomelo"
```

**Details**:

**`app/models/merchant.py`**:
- Class Merchant(Base, TimestampMixin, SoftDeleteMixin):
  - id: UUID (primary key, default=uuid4)
  - name: String(255) (UPPERCASE via __init__ or event listener)
  - provider: String(50) (e.g., "pomelo", "stripe")
  - embedding: Vector(1536) | None
  - logo_url: String(500) | None
  - weight: Float = 1.0
  - metadata: JSON (dict for mcc_type, voucher_type, etc.)
  - external_merchants: relationship("ExternalMerchant", back_populates="merchant")
  - mccs: relationship("Mcc", secondary="merchant_mcc", back_populates="merchants")
  - outbox_events: relationship("OutboxEvent", back_populates="merchant")
  - Event listener in __mapper_args__:
    - before_insert, before_update: name = name.upper() if name else None

**`app/repositories/merchant_repository.py`**:
- Class MerchantRepository:
  - __init__(self, session: AsyncSession | None = None)
  - _get_session() → get session from context or parameter
  - async create(merchant: Merchant) → Merchant
  - async get_by_id(id: UUID) → Merchant | None
  - async get_by_name(name: str) → Merchant | None
  - async list_all(skip: int, limit: int) → list[Merchant]
  - async search_by_similarity(embedding: list[float], threshold: float, limit: int) → list[tuple[Merchant, float]]
  - async update(id: UUID, **kwargs) → Merchant
  - async delete(id: UUID) → bool
  - async bulk_create(merchants: list[Merchant]) → list[Merchant]
  - All methods use _get_session() to pull ambient session from context

---

### Task 3.4: Implement MCC, Category & MerchantMcc Models + Repository
**Spec Requirement**: Merchant category codes (capability 2)  
**Depends On**: Task 3.1  
**Delivery**: `app/models/mcc.py`, `app/repositories/mcc_repository.py`  
**Verification**:
```bash
cd payments-mcc-classification && python -c "
from app.models import Mcc, Category
c = Category(name='FOOD')
print(c.name)
"
# Should print "FOOD"
```

**Details**:

**`app/models/mcc.py`**:
- Class Category(Base, TimestampMixin):
  - id: UUID (primary key)
  - name: String(100) unique
  - description: String(500) | None
  - mccs: relationship("Mcc", back_populates="category")
- Class Mcc(Base, TimestampMixin, SoftDeleteMixin):
  - id: UUID (primary key)
  - code: String(10) unique (e.g., "5411")
  - description: String(255)
  - category_id: UUID (foreign key to Category)
  - category: relationship("Category", back_populates="mccs")
  - embedding: Vector(768) | None
  - merchants: relationship("Merchant", secondary="merchant_mcc", back_populates="mccs")
- Class MerchantMcc(Base, TimestampMixin):
  - id: UUID (primary key)
  - merchant_id: UUID (foreign key, composite key with mcc_id)
  - mcc_id: UUID (foreign key, composite key with merchant_id)
  - merchant: relationship("Merchant")
  - mcc: relationship("Mcc")
  - unique constraint: (merchant_id, mcc_id)

**`app/repositories/mcc_repository.py`**:
- Class MccRepository:
  - async create(mcc: Mcc) → Mcc
  - async get_by_id(id: UUID) → Mcc | None
  - async get_by_code(code: str) → Mcc | None
  - async list_all(skip: int, limit: int) → list[Mcc]
  - async search_by_similarity(embedding: list[float], threshold: float, limit: int) → list[tuple[Mcc, float]]
  - async update(id: UUID, **kwargs) → Mcc
  - async delete(id: UUID) → bool
  - async add_merchant_to_mcc(mcc_id: UUID, merchant_id: UUID) → MerchantMcc
  - async remove_merchant_from_mcc(mcc_id: UUID, merchant_id: UUID) → bool
- Class CategoryRepository:
  - async create(category: Category) → Category
  - async get_by_id(id: UUID) → Category | None
  - async get_by_name(name: str) → Category | None
  - async list_all() → list[Category]

---

### Task 3.5: Implement ExternalMerchant & FailedMerchantCreation Models + Repository
**Spec Requirement**: External provider mapping, creation error tracking  
**Depends On**: Task 3.1  
**Delivery**: `app/models/external_merchant.py`, `app/repositories/external_merchant_repository.py`  
**Verification**:
```bash
cd payments-mcc-classification && python -c "
from app.models import ExternalMerchant
em = ExternalMerchant(provider='pomelo', provider_id='123')
print(em.provider, em.provider_id)
"
# Should print "pomelo 123"
```

**Details**:

**`app/models/external_merchant.py`**:
- Class ExternalMerchant(Base, TimestampMixin, SoftDeleteMixin):
  - Composite primary key: (provider, provider_id)
  - provider: String(50)
  - provider_id: String(255)
  - merchant_id: UUID | None (foreign key to Merchant, optional initially)
  - raw_data: JSON (original data from provider)
  - normalized_data: JSON (cleaned data for processing)
  - merchant: relationship("Merchant", foreign_keys=[merchant_id])
  - __table_args__ = (UniqueConstraint("provider", "provider_id"),)
- Class FailedMerchantCreation(Base, TimestampMixin):
  - id: UUID
  - external_merchant_id: UUID (composite foreign key)
  - external_merchant_provider: String(50) (composite foreign key)
  - error_message: Text
  - retry_count: Integer = 0
  - last_retry_at: DateTime | None
  - next_retry_at: DateTime | None
  - dead_lettered: Boolean = False
  - __table_args__ = (ForeignKeyConstraint([external_merchant_provider, external_merchant_id], ...),)

**`app/repositories/external_merchant_repository.py`**:
- Class ExternalMerchantRepository:
  - async create(external_merchant: ExternalMerchant) → ExternalMerchant
  - async get_by_provider_id(provider: str, provider_id: str) → ExternalMerchant | None
  - async get_by_merchant_id(merchant_id: UUID) → list[ExternalMerchant]
  - async list_all(skip: int, limit: int) → list[ExternalMerchant]
  - async update(provider: str, provider_id: str, **kwargs) → ExternalMerchant
  - async delete(provider: str, provider_id: str) → bool
  - async associate_merchant(provider: str, provider_id: str, merchant_id: UUID) → ExternalMerchant
- Class FailedMerchantCreationRepository:
  - async create(failed: FailedMerchantCreation) → FailedMerchantCreation
  - async get_by_id(id: UUID) → FailedMerchantCreation | None
  - async list_retryable(limit: int) → list[FailedMerchantCreation]
  - async update_retry(id: UUID, retry_count: int, last_retry_at: DateTime, next_retry_at: DateTime) → FailedMerchantCreation
  - async mark_dead_lettered(id: UUID) → FailedMerchantCreation

---

### Task 3.6: Implement Embedding & Outbox Models + Repository
**Spec Requirement**: Embedding similarity search (capability 3), reliable event delivery (capability 9)  
**Depends On**: Task 3.1  
**Delivery**: `app/models/embedding.py`, `app/models/outbox.py`, `app/repositories/embedding_repository.py`, `app/repositories/outbox_repository.py`  
**Verification**:
```bash
cd payments-mcc-classification && python -c "
from app.models import Embedding, OutboxEvent
e = Embedding(resource_type='merchant', resource_id='123', embedding=[0.1]*1536)
print(e.resource_type, len(e.embedding))
"
# Should print "merchant 1536"
```

**Details**:

**`app/models/embedding.py`**:
- Class Embedding(Base, TimestampMixin):
  - id: UUID
  - resource_type: String(50) (e.g., "merchant", "mcc")
  - resource_id: UUID
  - embedding: Vector(1536)
  - metadata: JSON | None (optional tags, context)

**`app/models/outbox.py`**:
- Class OutboxEvent(Base, TimestampMixin):
  - id: UUID
  - aggregate_type: String(50) (e.g., "Merchant")
  - aggregate_id: UUID
  - event_type: String(100) (e.g., "MerchantCreated")
  - payload: JSON
  - status: String(20) enum: "PENDING", "DELIVERED", "FAILED", "DEAD_LETTERED"
  - retry_count: Integer = 0
  - last_error: Text | None
  - delivered_at: DateTime | None
  - next_retry_at: DateTime | None
  - merchant_id: UUID | None (foreign key, optional)
  - merchant: relationship("Merchant", back_populates="outbox_events", foreign_keys=[merchant_id])

**`app/repositories/embedding_repository.py`**:
- Class EmbeddingRepository:
  - async create(embedding: Embedding) → Embedding
  - async get_by_resource(resource_type: str, resource_id: UUID) → Embedding | None
  - async search_similar(query_embedding: list[float], resource_type: str, threshold: float, limit: int) → list[tuple[Embedding, float]]
  - async upsert(resource_type: str, resource_id: UUID, embedding: list[float]) → Embedding
  - async delete(resource_type: str, resource_id: UUID) → bool

**`app/repositories/outbox_repository.py`**:
- Class OutboxRepository:
  - async create(event: OutboxEvent) → OutboxEvent
  - async get_by_id(id: UUID) → OutboxEvent | None
  - async list_pending(limit: int) → list[OutboxEvent]
  - async update_status(id: UUID, status: str, retry_count: int, last_error: str | None, delivered_at: DateTime | None) → OutboxEvent
  - async mark_delivered(id: UUID) → OutboxEvent
  - async mark_failed(id: UUID, error: str, next_retry_at: DateTime) → OutboxEvent
  - async mark_dead_lettered(id: UUID) → OutboxEvent

---

### Task 3.7: Run Initial Alembic Migration & Verify Schema
**Spec Requirement**: All 9 entities persisted to PostgreSQL  
**Depends On**: Tasks 3.3–3.6 (all models defined)  
**Delivery**: `alembic/versions/001_initial.py` (auto-generated)  
**Verification**:
```bash
cd payments-mcc-classification
alembic revision --autogenerate -m "initial schema"
alembic upgrade head
docker-compose exec postgres psql -U postgres -d merchant_db -c "\dt"
# Should list: merchant, mcc, category, merchant_mcc, external_merchant, failed_merchant_creation, embedding, outbox_event
```

**Details**:
- Run alembic auto-generate to create initial migration based on all model definitions
- Verify constraints:
  - Primary keys on all tables
  - Foreign keys with ON DELETE CASCADE where appropriate
  - Unique constraints (Category.name, Mcc.code, ExternalMerchant composite)
  - Vector column types created with pgvector extension
  - created_at, updated_at, deleted_at columns present
- Create indexes:
  - merchant.name (for LIKE queries)
  - merchant.embedding (pgvector ivfflat index)
  - mcc.code (unique)
  - external_merchant (provider, provider_id composite)
  - outbox_event.status, next_retry_at (for polling)
- Test migration:
  - Create fresh DB, run upgrade head, verify all tables present
  - Test rollback (down), verify all tables dropped
  - Test re-apply (up), verify idempotent

---

## Phase 4: Engine & Providers (9 tasks)

*Tasks **1** is prerequisite. Tasks **2–9** can parallelize after task 1 completes.*

### Task 4.1: Implement Pipeline Engine Framework
**Spec Requirement**: @step decorator, registry system, PipelineEngine (capability 4)  
**Depends On**: Task 2.1  
**Delivery**: `app/pipeline/engine.py`, `app/pipeline/decorators.py`, `app/pipeline/registry.py`  
**Verification**:
```bash
cd payments-mcc-classification && python -c "
from app.pipeline.decorators import step, ExecutionType
from app.pipeline.engine import PipelineEngine

@step(registry='test', order=1, execution_type=ExecutionType.BLOCKING)
class TestStep:
    async def execute(self, context):
        return {'result': 'ok'}

print(TestStep.__name__)
"
# Should print "TestStep"
```

**Details**:

**`app/pipeline/registry.py`**:
- Enum `ExecutionType`:
  - BLOCKING = "blocking" (sequential, participates in transaction)
  - NON_BLOCKING = "non_blocking" (fire-and-forget, asyncio task)
- Dict STEP_REGISTRY:
  - Key: (registry_name, order)
  - Value: list of step classes
  - Example: ("auto_creation", 1) → [CheckExistenceStep]
- Registry operations:
  - register_step(registry: str, order: int, step_class)
  - get_steps(registry: str) → sorted list by order
  - get_registry_names() → list of available registries

**`app/pipeline/decorators.py`**:
- Decorator `@step(registry: str, order: int, execution_type: ExecutionType, timeout: int = 30)`:
  - Must decorate a class with async execute(self, context) method
  - Call register_step(registry, order, class)
  - Add metadata to class: __step_registry__, __step_order__, __execution_type__, __step_timeout__
  - Validation: class must have execute method
  - Return unmodified class

**`app/pipeline/engine.py`**:
- Class `PipelineContext`:
  - Fields:
    - data: dict (mutable state shared across steps)
    - session: AsyncSession (from context var)
    - logger: structlog logger
    - step_results: dict[str, dict] (per-step output)
    - start_time: datetime
    - cancelled: bool = False
  - Methods:
    - should_run(step_class) → call step.should_run(self) if exists, else True
    - log(level: str, msg: str, **kwargs) → structlog logging
- Class `PipelineEngine`:
  - async run(registry: str, context: PipelineContext) → dict:
    - Get all steps for registry via get_steps(registry)
    - For each step (in order):
      - If should_run(step) returns False, skip
      - If execution_type == BLOCKING:
        - Instantiate step(), call execute(context), await result
        - Store result in context.step_results[step.__name__]
        - Catch exception, log, decide continue/fail based on error_handling
      - If execution_type == NON_BLOCKING:
        - Instantiate step(), create asyncio.Task(step.execute(context))
        - Add to pending tasks, don't await
    - After all blocking steps, gather all non-blocking tasks with asyncio.gather(timeout=max_timeout)
    - Return context
  - Error handling policy:
    - BLOCKING: exception re-raised (stops pipeline)
    - NON_BLOCKING: exception caught & logged, does not stop pipeline
  - Timeout: if step takes > timeout, cancel and log warning
- Base class `BaseStep`:
  - async execute(self, context: PipelineContext) → Any (abstract)
  - def should_run(self, context: PipelineContext) → bool (default True)

---

### Task 4.2: Implement ILlmProvider Interface & OpenAI Implementation
**Spec Requirement**: LLM provider abstraction, OpenAI + LangFuse (capability 5)  
**Depends On**: Task 2.1  
**Delivery**: `app/providers/llm/__init__.py`, `app/providers/llm/interface.py`, `app/providers/llm/openai_provider.py`  
**Verification**:
```bash
cd payments-mcc-classification && python -c "
from app.providers.llm.interface import ILlmProvider
from app.providers.llm.openai_provider import OpenAiProvider
provider = OpenAiProvider(api_key='test')
print(isinstance(provider, ILlmProvider))
"
# Should print "True"
```

**Details**:

**`app/providers/llm/interface.py`**:
- Abstract class `ILlmProvider`:
  - async generate(prompt: str, max_tokens: int = 1000, temperature: float = 0.7) → str
  - async embed(text: str) → list[float]
  - async research(query: str, max_results: int = 5) → str
  - property model_name: str

**`app/providers/llm/openai_provider.py`**:
- Class `OpenAiProvider(ILlmProvider)`:
  - __init__(api_key: str, model: str = "gpt-4-turbo-preview", embedding_model: str = "text-embedding-3-small"):
    - Store api_key
    - Initialize OpenAI client from openai.OpenAI(api_key)
    - Store model names
  - async generate(prompt: str, max_tokens: int, temperature: float) → str:
    - Call client.chat.completions.create(model, messages=[{"role": "user", "content": prompt}], max_tokens, temperature)
    - Return completion.choices[0].message.content
    - Emit LangFuse trace: trace(name="llm_generate", input=prompt, output=result)
  - async embed(text: str) → list[float]:
    - Call client.embeddings.create(model=embedding_model, input=text)
    - Return embedding vector (list[float])
    - Cache embeddings in simple dict to avoid re-computation (optional)
  - async research(query: str, max_results: int) → str:
    - Call Tavily API (or return empty string if TAVILY_API_KEY not set)
    - Format results as markdown string
  - property model_name → return self.model
- LangFuse callback:
  - If LANGFUSE_PUBLIC_KEY set:
    - Initialize LangFuseCallbackHandler
    - Attach to LangChain chains used in pipeline steps
  - Otherwise: no-op callback

---

### Task 4.3: Implement ICardProvider Interface & Pomelo Implementation
**Spec Requirement**: Card provider abstraction, Pomelo default (capability 6)  
**Depends On**: Task 2.1  
**Delivery**: `app/providers/card/__init__.py`, `app/providers/card/interface.py`, `app/providers/card/pomelo_provider.py`  
**Verification**:
```bash
cd payments-mcc-classification && python -c "
from app.providers.card.interface import ICardProvider
from app.providers.card.pomelo_provider import PomeloProvider
provider = PomeloProvider(api_key='test', base_url='https://api.pomelo.dev')
print(isinstance(provider, ICardProvider))
"
# Should print "True"
```

**Details**:

**`app/providers/card/interface.py`**:
- Abstract class `ICardProvider`:
  - async normalize_merchant(raw_data: dict) → dict (normalized ExternalMerchantDTO)
  - async get_transactions(filters: dict) → list[dict] (transaction data)
  - async lookup_merchant(name: str) → dict | None (external merchant data)
  - property provider_name: str

**`app/providers/card/pomelo_provider.py`**:
- Class `PomeloProvider(ICardProvider)`:
  - __init__(api_key: str, base_url: str = "https://api.pomelo.dev"):
    - Store api_key, base_url
    - Initialize httpx.AsyncClient with headers: {"Authorization": f"Bearer {api_key}"}
  - async normalize_merchant(raw_data: dict) → dict:
    - Extract: name, category, mcc_code, logo_url from raw_data
    - Uppercase name
    - Return {"name": ..., "provider": "pomelo", "provider_id": raw_data["id"], "mcc_code": ..., "logo_url": ...}
  - async get_transactions(filters: dict) → list[dict]:
    - Call GET /transactions with filters as query params
    - Return list of transaction dicts
    - Handle pagination (page_size=100, iterate)
  - async lookup_merchant(name: str) → dict | None:
    - Call GET /merchants/search?q={name}
    - Return first result or None
  - Error handling:
    - Catch httpx.HTTPError → log & re-raise as IntegrationError
    - Catch timeout → re-raise as IntegrationError("Pomelo timeout")
  - property provider_name → return "pomelo"

---

### Task 4.4: Implement Embedding Provider & pgvector Queries
**Spec Requirement**: Vector similarity search via pgvector (capability 3)  
**Depends On**: Task 3.3, 3.4, 3.6 (models defined)  
**Delivery**: `app/providers/embedding.py` (or extend embedding_repository.py)  
**Verification**:
```bash
cd payments-mcc-classification && python -c "
from app.providers.embedding import cosine_similarity
v1 = [1, 0, 0]
v2 = [1, 0, 0]
sim = cosine_similarity(v1, v2)
print(sim)
"
# Should print "1.0"
```

**Details**:
- Module `app/providers/embedding.py`:
  - Function `cosine_similarity(v1: list[float], v2: list[float]) -> float`:
    - Compute dot product / (norm(v1) * norm(v2))
    - Return float between -1 and 1
  - Function `store_embedding(resource_type: str, resource_id: UUID, embedding: list[float], session: AsyncSession) -> Embedding`:
    - Create/upsert Embedding record
    - Save to DB
  - Function `search_embeddings_by_similarity(query_embedding: list[float], resource_type: str, threshold: float, limit: int, session: AsyncSession) -> list[tuple[Embedding, float]]`:
    - Raw SQL using pgvector <-> operator (cosine distance): SELECT id, resource_id, embedding <-> %s AS distance ORDER BY distance LIMIT %s
    - Or use SQLAlchemy: session.query(Embedding).filter(Embedding.resource_type == resource_type).order_by(Embedding.embedding.op('<->', return_type=Float)).limit(limit)
    - Return list of (Embedding, similarity_score) tuples
    - Similarity = 1 - distance for cosine

---

### Task 4.5: Implement Google Places Provider (Optional, Non-Blocking)
**Spec Requirement**: Optional enrich merchant data via Google Places  
**Depends On**: Task 2.1  
**Delivery**: `app/providers/google_places.py`  
**Verification**:
```bash
cd payments-mcc-classification && python -c "
from app.providers.google_places import GooglePlacesProvider
provider = GooglePlacesProvider(api_key='test')
print(provider.provider_name)
"
# Should print "google_places"
```

**Details**:
- Class `GooglePlacesProvider`:
  - __init__(api_key: str):
    - Store api_key
    - Initialize httpx.AsyncClient
  - async lookup(query: str) → dict | None:
    - Call GET https://maps.googleapis.com/maps/api/place/findplacefromtext/json?input={query}&key={api_key}
    - Return first result with name, lat, lng, address, rating, review_count
    - Return None if no match
  - Error handling:
    - Catch httpx.HTTPError → log & return None (non-blocking)

---

### Task 4.6: Implement S3 Logo Storage Provider
**Spec Requirement**: Upload/download merchant logos  
**Depends On**: Task 2.1  
**Delivery**: `app/providers/s3.py`  
**Verification**:
```bash
cd payments-mcc-classification && python -c "
from app.providers.s3 import S3Provider
provider = S3Provider(access_key='test', secret_key='test', bucket='test')
print(provider.bucket)
"
# Should print "test"
```

**Details**:
- Class `S3Provider`:
  - __init__(access_key: str, secret_key: str, bucket: str, region: str = "us-east-1"):
    - Initialize boto3 S3 client with credentials
  - async upload_logo(merchant_id: UUID, image_bytes: bytes) → str:
    - Generate key: f"logos/{merchant_id}.png"
    - Call s3.put_object(Bucket=bucket, Key=key, Body=image_bytes, ContentType="image/png")
    - Return public URL: f"https://{bucket}.s3.{region}.amazonaws.com/{key}"
  - async download_logo(merchant_id: UUID) → bytes | None:
    - Call s3.get_object(Bucket=bucket, Key=f"logos/{merchant_id}.png")
    - Return Body as bytes
    - Return None if not found
  - Note: Actual implementation optional in v1; stub with NotImplementedError

---

### Task 4.7: Implement SNS Event Publisher
**Spec Requirement**: Publish events to AWS SNS (for integration with Voucher service)  
**Depends On**: Task 2.1  
**Delivery**: `app/providers/sns.py`  
**Verification**:
```bash
cd payments-mcc-classification && python -c "
from app.providers.sns import SnsPublisher
pub = SnsPublisher(topic_arn='arn:aws:sns:...')
print(pub.topic_arn)
"
# Should print (test ARN)
```

**Details**:
- Class `SnsPublisher`:
  - __init__(topic_arn: str, region: str = "us-east-1"):
    - Initialize boto3 SNS client
  - async publish(message: dict, event_type: str) → str:
    - Call sns.publish(TopicArn=topic_arn, Subject=event_type, Message=json.dumps(message))
    - Return MessageId
  - Error handling:
    - Catch botocore exceptions → log & re-raise as IntegrationError
  - Note: Actual AWS integration optional in v1; stub with NotImplementedError

---

### Task 4.8: Wire Providers into FastAPI Dependency Injection
**Spec Requirement**: All providers injectable via Depends()  
**Depends On**: Tasks 4.2–4.7, Task 2.1  
**Delivery**: `app/core/dependencies.py`  
**Verification**:
```bash
cd payments-mcc-classification && python -c "
from app.core.dependencies import get_llm_provider
from app.providers.llm.interface import ILlmProvider
provider = get_llm_provider()
print(isinstance(provider, ILlmProvider))
"
# Should print "True"
```

**Details**:
- Module `app/core/dependencies.py`:
  - Singleton pattern:
    - _llm_provider: ILlmProvider | None = None
    - _card_provider: ICardProvider | None = None
    - etc.
  - Functions:
    - def get_llm_provider() → ILlmProvider:
      - If _llm_provider is None, create OpenAiProvider(settings.openai_api_key)
      - Return _llm_provider
    - def get_card_provider() → ICardProvider:
      - If _card_provider is None, create PomeloProvider(settings.pomelo_api_key, settings.pomelo_base_url)
      - Return _card_provider
    - def get_embedding_provider() → EmbeddingProvider:
      - Similar pattern
    - def get_session() → AsyncSession:
      - Get ambient session from context, or create new from factory
  - Each function decorated with @lru_cache (for singletons) or returning fresh instance

---

### Task 4.9: Create Pipeline Step Base Class & Test Steps
**Spec Requirement**: BaseStep, should_run(), timeout handling  
**Depends On**: Task 4.1  
**Delivery**: `app/pipeline/base_step.py`  
**Verification**:
```bash
cd payments-mcc-classification && python -c "
from app.pipeline.base_step import BaseStep
class TestStep(BaseStep):
    async def execute(self, context):
        return {'ok': True}
print(TestStep.__name__)
"
# Should print "TestStep"
```

**Details**:
- Abstract class `BaseStep`:
  - __init__(self) (empty by default)
  - async execute(self, context: PipelineContext) → Any (must be overridden)
  - def should_run(self, context: PipelineContext) → bool:
    - Default: return True
    - Subclasses can override to conditionally skip
  - classmethod get_metadata(cls) → dict:
    - Return {registry, order, execution_type, timeout}
- Create stub test steps (e.g., for integration tests):
  - Step1(BaseStep): returns {"step": "1"}
  - Step2(BaseStep): returns {"step": "2", "input": context.data}

---

## Phase 5: API & Workers (16 tasks)

*Tasks **1–2** are sequential. Tasks **3–16** can parallelize after 2 completes.*

### Task 5.1: Create Pydantic Schemas (Request/Response DTOs)
**Spec Requirement**: Type-safe API validation (FastAPI Merchant API, MCC, etc.)  
**Depends On**: Task 2.1  
**Delivery**: `app/schemas/__init__.py` with all DTO classes  
**Verification**:
```bash
cd payments-mcc-classification && python -c "
from app.schemas import MerchantCreateRequest
m = MerchantCreateRequest(name='Test', provider='pomelo')
print(m.name, m.provider)
"
# Should print "Test pomelo"
```

**Details**:
- Module `app/schemas/__init__.py`:
  - Import/export all schema classes
- Class `MerchantCreateRequest`:
  - name: str (min_length=1, max_length=255)
  - provider: str (enum: "pomelo", "stripe", etc.)
  - mcc_codes: list[str] | None
  - logo_url: str | None (URL format)
  - metadata: dict[str, Any] | None
- Class `MerchantResponse`:
  - id: UUID
  - name: str
  - provider: str
  - embedding: list[float] | None (excluded by default)
  - logo_url: str | None
  - weight: float
  - metadata: dict
  - created_at: datetime
  - updated_at: datetime
- Class `MerchantListResponse`:
  - items: list[MerchantResponse]
  - total: int
  - skip: int
  - limit: int
- Classes:
  - `MccCreateRequest`, `MccResponse`, `MccListResponse`
  - `CategoryCreateRequest`, `CategoryResponse`
  - `ExternalMerchantCreateRequest`, `ExternalMerchantResponse`
  - `EmbeddingSearchRequest`, `EmbeddingSearchResponse`
  - `OutboxEventResponse`, `OutboxEventListResponse`
  - `ErrorResponse`: message, error_code, details
- Config:
  - from_attributes = True (for ORM model serialization)
  - arbitrary_types_allowed = True (for UUID, datetime)

---

### Task 5.2: Create Core Services Orchestration Layer
**Spec Requirement**: Stateless business logic services  
**Depends On**: Tasks 3.3–3.6, 4.8  
**Delivery**: `app/services/merchant_service.py`, `app/services/mcc_service.py`, `app/services/external_merchant_service.py`  
**Verification**:
```bash
cd payments-mcc-classification && python -c "
from app.services.merchant_service import MerchantService
service = MerchantService(None)
print(service.__class__.__name__)
"
# Should print "MerchantService"
```

**Details**:

**`app/services/merchant_service.py`**:
- Class `MerchantService`:
  - __init__(llm_provider: ILlmProvider = Depends(...)):
    - Store provider
  - @transactional
  - async create(request: MerchantCreateRequest) → Merchant:
    - Validate name (not empty)
    - Check for duplicates (get_by_name)
    - Create Merchant record
    - If request.mcc_codes provided, add MCCs via mcc_repo.add_merchant_to_mcc()
    - Generate embedding via llm_provider.embed(name)
    - Save embedding to Embedding table
    - Return created merchant
  - @transactional
  - async get_by_id(id: UUID) → Merchant:
    - Call merchant_repo.get_by_id(id)
    - Return or raise ResourceNotFound
  - @transactional
  - async list_all(skip: int = 0, limit: int = 100) → list[Merchant]:
    - Validate skip, limit (limit max 500)
    - Call merchant_repo.list_all(skip, limit)
  - @transactional
  - async update(id: UUID, request: MerchantUpdateRequest) → Merchant:
    - Fetch merchant via get_by_id
    - Update fields (name, logo_url, weight, metadata)
    - If name changed, regenerate embedding
    - Save
    - Return updated merchant
  - @transactional
  - async delete(id: UUID) → bool:
    - Fetch merchant
    - Set soft delete (deleted_at = now)
    - Return True
  - @transactional
  - async bulk_create(requests: list[MerchantCreateRequest]) → list[Merchant]:
    - Create multiple merchants
    - Use bulk_create for batch insert if available
  - @transactional
  - async search_by_similarity(query: str, threshold: float = 0.7, limit: int = 10) → list[tuple[Merchant, float]]:
    - Generate embedding for query via llm_provider.embed(query)
    - Call merchant_repo.search_by_similarity(embedding, threshold, limit)
    - Return results with similarity scores
  - async assign_mcc(merchant_id: UUID, mcc_id: UUID) → MerchantMcc:
    - Validate both exist
    - Call mcc_repo.add_merchant_to_mcc()
    - Return join record

**`app/services/mcc_service.py`**:
- Class `MccService`:
  - __init__(llm_provider: ILlmProvider = Depends(...))
  - @transactional
  - async create(request: MccCreateRequest) → Mcc:
    - Check code unique
    - Create Mcc
    - Generate embedding via llm_provider.embed(description)
    - Return
  - @transactional
  - async get_by_id(id: UUID) → Mcc:
    - Call mcc_repo.get_by_id(id)
    - Return or raise ResourceNotFound
  - @transactional
  - async get_by_code(code: str) → Mcc:
    - Call mcc_repo.get_by_code(code)
    - Return or raise ResourceNotFound
  - @transactional
  - async list_all(skip: int = 0, limit: int = 100) → list[Mcc]:
    - Call mcc_repo.list_all(skip, limit)
  - @transactional
  - async update(id: UUID, request: MccUpdateRequest) → Mcc:
    - Fetch, update, regenerate embedding if description changed
    - Return
  - @transactional
  - async delete(id: UUID) → bool:
    - Soft delete
    - Return True
  - @transactional
  - async search_by_similarity(query: str, threshold: float = 0.7, limit: int = 10) → list[tuple[Mcc, float]]:
    - Generate embedding, search
    - Return results
  - async create_category(request: CategoryCreateRequest) → Category:
    - Check name unique
    - Create Category
    - Return
  - async get_category_by_id(id: UUID) → Category:
    - Call category_repo.get_by_id(id)
  - async list_categories() → list[Category]:
    - Call category_repo.list_all()

**`app/services/external_merchant_service.py`**:
- Class `ExternalMerchantService`:
  - __init__(card_provider: ICardProvider = Depends(...))
  - @transactional
  - async register(provider: str, provider_id: str, raw_data: dict) → ExternalMerchant:
    - Check not already registered (get_by_provider_id)
    - Normalize data via card_provider.normalize_merchant(raw_data)
    - Create ExternalMerchant record (raw_data + normalized_data)
    - Return
  - @transactional
  - async get_by_provider_id(provider: str, provider_id: str) → ExternalMerchant:
    - Call external_merchant_repo.get_by_provider_id(provider, provider_id)
  - @transactional
  - async list_all(skip: int = 0, limit: int = 100) → list[ExternalMerchant]:
    - Call external_merchant_repo.list_all(skip, limit)
  - @transactional
  - async associate_merchant(provider: str, provider_id: str, merchant_id: UUID) → ExternalMerchant:
    - Fetch external merchant
    - Check merchant exists
    - Update external_merchant.merchant_id
    - Create Outbox event: ExternalMerchantAssociated
    - Return
  - async delete(provider: str, provider_id: str) → bool:
    - Call external_merchant_repo.delete(provider, provider_id)

---

### Task 5.3: Implement Auto-Creation Pipeline Steps
**Spec Requirement**: 7-step auto-creation sequence (capability 8, design detail)  
**Depends On**: Task 4.1, 5.2  
**Delivery**: `app/pipeline/auto_creation/__init__.py` with all 7 steps  
**Verification**:
```bash
cd payments-mcc-classification && python -c "
from app.pipeline.auto_creation import CheckExistenceStep
print(CheckExistenceStep.__name__)
"
# Should print "CheckExistenceStep"
```

**Details**:

Create 7 step classes (each in separate file, imported in `__init__.py`):

1. **CheckExistenceStep** (order=1, blocking):
   - Check if merchant with same name/provider already exists
   - should_run: only if data.merchant not set
   - execute: query merchant_repo.get_by_name(data['name'])
   - If found: set context.data['merchant'] = existing, return {found: True}
   - Else: return {found: False}

2. **LlmResearchStep** (order=2, blocking):
   - Use LLM to research merchant via Tavily
   - should_run: only if data.merchant is None
   - execute: call llm_provider.research(data['name'])
   - return {research_result: ...}

3. **GenerateEmbeddingStep** (order=3, blocking):
   - Generate embedding for merchant name
   - execute: call llm_provider.embed(data['name'])
   - Set data['embedding'] = result
   - return {embedding_generated: True}

4. **GooglePlacesEnrichmentStep** (order=4, non-blocking):
   - Optional: enrich with Google Places data
   - execute: call google_places.lookup(data['name'])
   - Merge results into data['location_metadata']
   - return {google_place_enriched: True/False}

5. **MccClassificationStep** (order=5, blocking):
   - Classify merchant MCC via LLM
   - execute: prompt LLM with merchant description
   - Parse response: mcc_code, category
   - Verify MCC exists in DB
   - return {mcc_code: ..., confidence: ...}

6. **CreateMerchantStep** (order=6, blocking):
   - Create Merchant record with all data
   - execute:
     - Build Merchant object from data
     - Call merchant_repo.create()
     - Assign MCCs via mcc_service.assign_mcc()
     - Store embedding
     - Set data['merchant'] = created merchant
     - Create Outbox event: MerchantCreated
   - return {merchant_id: ..., created: True}

7. **NotifyDownstreamStep** (order=7, non-blocking):
   - Publish to SNS / call downstream services
   - execute: call sns_publisher.publish(merchant_data, "MerchantCreated")
   - return {notification_sent: True}

---

### Task 5.4: Implement Validation Pipeline Steps
**Spec Requirement**: Multi-step validation engine (design detail)  
**Depends On**: Task 4.1, 5.2  
**Delivery**: `app/pipeline/validation/__init__.py` with validation steps  
**Verification**:
```bash
cd payments-mcc-classification && python -c "
from app.pipeline.validation import ValidateNameStep
print(ValidateNameStep.__name__)
"
# Should print "ValidateNameStep"
```

**Details**:

Create validation step classes:

1. **ValidateNameStep** (order=1, blocking):
   - Check name format, length, special chars
   - execute: validate name per business rules
   - should_run: if data['name'] is not None
   - raise ValidationFailed if invalid

2. **ValidateMccStep** (order=2, blocking):
   - Verify MCC codes exist in DB
   - execute: for each mcc_code, call mcc_repo.get_by_code()
   - raise ValidationFailed if not found

3. **CheckDuplicateStep** (order=3, blocking):
   - Verify merchant not already registered
   - execute: check by name + provider combo
   - raise ConflictError if duplicate

---

### Task 5.5: Create Merchant FastAPI Router (/v1/merchants)
**Spec Requirement**: 6 endpoints for CRUD + bulk + search (FastAPI Merchant API)  
**Depends On**: Task 5.1, 5.2, 4.8  
**Delivery**: `app/api/v1/merchants.py`  
**Verification**:
```bash
cd payments-mcc-classification && python -c "
from app.api.v1.merchants import router
print(len(router.routes))
"
# Should have 6+ routes
```

**Details**:
- Router `prefix="/merchants"`, tags=["merchants"]
- Endpoints:
  1. **POST /v1/merchants** (create):
     - Body: MerchantCreateRequest
     - Return: MerchantResponse (201)
     - Dependency: @require_hmac_auth, @transactional
  2. **GET /v1/merchants/{id}** (get by id):
     - Param: id (UUID)
     - Return: MerchantResponse (200)
     - 404 if not found
  3. **GET /v1/merchants** (list):
     - Query: skip (int=0), limit (int=100)
     - Return: MerchantListResponse (200)
  4. **PATCH /v1/merchants/{id}** (update):
     - Body: MerchantUpdateRequest (partial)
     - Return: MerchantResponse (200)
  5. **DELETE /v1/merchants/{id}** (soft delete):
     - Return: 204 No Content
  6. **POST /v1/merchants/bulk** (bulk create):
     - Body: list[MerchantCreateRequest]
     - Return: list[MerchantResponse] (201)
  7. **POST /v1/merchants/search** (similarity search):
     - Body: {query: str, threshold: float, limit: int}
     - Return: list[{merchant: MerchantResponse, score: float}] (200)
  8. **POST /v1/merchants/{id}/mcc/{mcc_id}** (assign MCC):
     - Return: MerchantResponse (200)

---

### Task 5.6: Create MCC FastAPI Router (/v1/mcc)
**Spec Requirement**: CRUD + similarity search for MCCs  
**Depends On**: Task 5.1, 5.2, 4.8  
**Delivery**: `app/api/v1/mccs.py`  
**Verification**:
```bash
cd payments-mcc-classification && python -c "
from app.api.v1.mccs import router
print(len(router.routes))
"
# Should have 6+ routes
```

**Details**:
- Router `prefix="/mcc"`, tags=["mcc"]
- Endpoints:
  1. **POST /v1/mcc** (create):
     - Body: MccCreateRequest
     - Return: MccResponse (201)
  2. **GET /v1/mcc/{id}** (get by id):
     - Return: MccResponse (200)
  3. **GET /v1/mcc** (list):
     - Query: skip, limit
     - Return: MccListResponse (200)
  4. **GET /v1/mcc/code/{code}** (get by code):
     - Return: MccResponse (200)
  5. **PATCH /v1/mcc/{id}** (update):
     - Body: MccUpdateRequest
     - Return: MccResponse (200)
  6. **DELETE /v1/mcc/{id}** (soft delete):
     - Return: 204 No Content
  7. **POST /v1/mcc/search** (similarity search):
     - Body: {query: str, threshold: float, limit: int}
     - Return: list[{mcc: MccResponse, score: float}] (200)
  8. **POST /v1/categories** (create category):
     - Body: CategoryCreateRequest
     - Return: CategoryResponse (201)
  9. **GET /v1/categories** (list categories):
     - Return: list[CategoryResponse] (200)

---

### Task 5.7: Create External Merchant FastAPI Router (/v1/external-merchants)
**Spec Requirement**: External merchant registration & association  
**Depends On**: Task 5.1, 5.2, 4.8  
**Delivery**: `app/api/v1/external_merchants.py`  
**Verification**:
```bash
cd payments-mcc-classification && python -c "
from app.api.v1.external_merchants import router
print(len(router.routes))
"
# Should have 4+ routes
```

**Details**:
- Router `prefix="/external-merchants"`, tags=["external-merchants"]
- Endpoints:
  1. **POST /v1/external-merchants** (register):
     - Body: ExternalMerchantCreateRequest (provider, provider_id, raw_data)
     - Return: ExternalMerchantResponse (201)
  2. **GET /v1/external-merchants/{provider}/{provider_id}** (get by provider id):
     - Return: ExternalMerchantResponse (200)
  3. **GET /v1/external-merchants** (list):
     - Query: skip, limit
     - Return: list[ExternalMerchantResponse] (200)
  4. **POST /v1/external-merchants/{provider}/{provider_id}/associate** (link to merchant):
     - Body: {merchant_id: UUID}
     - Return: ExternalMerchantResponse (200)
  5. **DELETE /v1/external-merchants/{provider}/{provider_id}** (soft delete):
     - Return: 204 No Content

---

### Task 5.8: Create Auto-Creation Pipeline Endpoint (/v1/merchants/auto-create)
**Spec Requirement**: Trigger auto-creation pipeline via API  
**Depends On**: Task 5.3, 4.8  
**Delivery**: `app/api/v1/auto_creation.py`  
**Verification**:
```bash
cd payments-mcc-classification && python -c "
from app.api.v1.auto_creation import router
print(len(router.routes))
"
# Should have 1-2 routes
```

**Details**:
- Router `prefix="/merchants"`, tags=["auto-creation"]
- Endpoints:
  1. **POST /v1/merchants/auto-create** (start pipeline):
     - Body: {name: str, provider: str, raw_data: dict}
     - Execution: Inject data into PipelineContext, call PipelineEngine.run("auto_creation", context)
     - Return: PipelineResultResponse {merchant_id, steps_completed: list, errors: list} (201 or 400)
  2. **POST /v1/merchants/validate** (validate raw merchant data):
     - Body: {name: str, provider: str, raw_data: dict}
     - Execution: Run validation pipeline
     - Return: ValidationResultResponse {valid: bool, errors: list[str]} (200)

---

### Task 5.9: Create Health Check Router (/health)
**Spec Requirement**: Readiness + liveness probes  
**Depends On**: Task 2.5, 2.3  
**Delivery**: `app/api/v1/health.py`  
**Verification**:
```bash
cd payments-mcc-classification && python -c "
from app.api.v1.health import router
print(len(router.routes))
"
# Should have 2 routes
```

**Details**:
- Router unprotected (no HMAC requirement)
- Endpoints:
  1. **GET /health** (liveness):
     - Return: {status: "ok"} (200)
  2. **GET /health/ready** (readiness):
     - Check DB connection: async with get_db_session() as session: await session.execute("SELECT 1")
     - Check LLM provider: call get_llm_provider()
     - Return: {status: "ready", db: "ok", llm: "ok", timestamp: now} (200 or 503)

---

### Task 5.10: Create Embedding Search Endpoint (/v1/embeddings/search)
**Spec Requirement**: Cross-resource embedding similarity search  
**Depends On**: Task 5.1, 4.4  
**Delivery**: `app/api/v1/embeddings.py`  
**Verification**:
```bash
cd permissions-classification-mcp && python -c "
from app.api.v1.embeddings import router
print(len(router.routes))
"
# Should have 1 route
```

**Details**:
- Router `prefix="/embeddings"`, tags=["embeddings"]
- Endpoints:
  1. **POST /v1/embeddings/search** (search merchants + mccs):
     - Body: {query: str, resource_types: list["merchant"|"mcc"], threshold: float, limit: int}
     - Execution: Generate embedding for query, search both resource types
     - Return: {merchants: list[...], mccs: list[...]} (200)

---

### Task 5.11: Create Outbox Event Endpoint (/v1/outbox)
**Spec Requirement**: Monitor event delivery status  
**Depends On**: Task 5.1, 5.2  
**Delivery**: `app/api/v1/outbox.py`  
**Verification**:
```bash
cd payments-mcc-classification && python -c "
from app.api.v1.outbox import router
print(len(router.routes))
"
# Should have 2 routes
```

**Details**:
- Router `prefix="/outbox"`, tags=["outbox"]
- Endpoints:
  1. **GET /v1/outbox** (list events):
     - Query: status (pending|delivered|failed), skip, limit
     - Return: OutboxEventListResponse (200)
  2. **GET /v1/outbox/{id}** (get event):
     - Return: OutboxEventResponse (200)
  3. **POST /v1/outbox/{id}/retry** (retry failed event):
     - Return: OutboxEventResponse (200)

---

### Task 5.12: Wire All Routers into FastAPI App
**Spec Requirement**: Main app factory with all middleware + routes  
**Depends On**: Tasks 5.5–5.11, 2.1, 2.3, 2.4  
**Delivery**: `app/main.py` (updated) with full app bootstrap  
**Verification**:
```bash
cd payments-mcc-classification && python -c "
from app.main import create_app
app = create_app()
print(len(app.routes))
"
# Should have 20+ routes
```

**Details**:
- Function `create_app() -> FastAPI`:
  - app = FastAPI(title="payments-mcc-classification", version="1.0.0")
  - Middleware:
    - app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
    - app.add_middleware(TrustedHostMiddleware, allowed_hosts=[...])
    - Custom middleware for request logging (request_id, method, path, duration)
  - Exception handlers:
    - app.exception_handler(AppException)
    - app.exception_handler(RequestValidationError)
  - Startup/shutdown:
    - @app.on_event("startup"): init_db(), start_outbox_worker()
    - @app.on_event("shutdown"): stop_outbox_worker(), close_db()
  - Include routers:
    - app.include_router(health_router, prefix="/api")
    - app.include_router(merchants_router, prefix="/api/v1")
    - app.include_router(mccs_router, prefix="/api/v1")
    - app.include_router(external_merchants_router, prefix="/api/v1")
    - app.include_router(auto_creation_router, prefix="/api/v1")
    - app.include_router(embeddings_router, prefix="/api/v1")
    - app.include_router(outbox_router, prefix="/api/v1")
  - Return app

---

### Task 5.13: Implement Outbox Processor Worker
**Spec Requirement**: Reliable async event delivery with retry (capability 9)  
**Depends On**: Task 3.6, 4.8  
**Delivery**: `app/workers/outbox_processor.py`  
**Verification**:
```bash
cd payments-mcc-classification && python -c "
from app.workers.outbox_processor import AsyncOutboxProcessor
print(AsyncOutboxProcessor.__name__)
"
# Should print "AsyncOutboxProcessor"
```

**Details**:
- Class `AsyncOutboxProcessor`:
  - __init__(session_factory, voucher_service_url: str, poll_interval: int = 2):
    - Store session_factory, voucher_service_url, poll_interval
    - _running: bool = False
    - _tasks: set = set()
  - async start():
    - Set _running = True
    - Launch event_loop task: asyncio.create_task(self._poll_loop())
  - async stop():
    - Set _running = False
    - await asyncio.gather(*_tasks) to wait for completion
  - async _poll_loop():
    - While _running:
      - Try:
        - Call _fetch_and_process_pending()
        - await asyncio.sleep(poll_interval)
      - Except Exception: log, continue
  - async _fetch_and_process_pending():
    - async with session_factory() as session:
      - Query Outbox table: status='PENDING' ORDER BY created_at LIMIT 10
      - For each event:
        - Task: asyncio.create_task(self._process_event(event, session))
        - _tasks.add(task)
      - await asyncio.gather(*pending_tasks) with timeout=max(timeout, 30s)
  - async _process_event(event, session):
    - Try:
      - Parse event.payload
      - Call appropriate handler (MerchantCreated → notify Voucher service, etc.)
      - Call outbox_repo.mark_delivered(event.id)
    - Except Exception as e:
      - Increment retry_count
      - Compute next_retry_at: now + backoff(retry_count) [1s, 2s, 4s, 8s, 16s, 32s]
      - If retry_count >= 6: mark_dead_lettered
      - Else: mark_failed(event.id, str(e), next_retry_at)
      - Log
  - Event handlers:
    - async _handle_merchant_created(event):
      - POST to Voucher service: POST /vouchers/merchants
      - Wait for 200 status
    - async _handle_merchant_updated(event): similar
    - async _handle_merchant_deleted(event): similar

---

### Task 5.14: Implement Startup/Shutdown Hooks
**Spec Requirement**: Initialize DB, start worker, cleanup on exit  
**Depends On**: Task 5.13, 2.5  
**Delivery**: `app/core/lifecycle.py`  
**Verification**:
```bash
cd payments-mcc-classification && python -c "
from app.core.lifecycle import init_app, shutdown_app
print(init_app.__name__, shutdown_app.__name__)
"
# Should print "init_app shutdown_app"
```

**Details**:
- Module `app/core/lifecycle.py`:
  - Global variable: _outbox_processor: AsyncOutboxProcessor | None = None
  - async init_app():
    - Log "Starting application..."
    - Call init_db() → run migrations (alembic upgrade head)
    - Create AsyncOutboxProcessor
    - Call processor.start()
    - Set _outbox_processor = processor
    - Log "Application started"
  - async shutdown_app():
    - Log "Shutting down application..."
    - If _outbox_processor:
      - Call _outbox_processor.stop()
    - Close DB connections
    - Log "Application shut down"

---

### Task 5.15: Create FastAPI Exception Handling Middleware
**Spec Requirement**: Consistent error responses for all exceptions  
**Depends On**: Task 2.3, 2.1  
**Delivery**: `app/core/middleware.py`  
**Verification**:
```bash
cd payments-mcc-classification && python -c "
from app.core.middleware import setup_exception_handlers
print(setup_exception_handlers.__name__)
"
# Should print "setup_exception_handlers"
```

**Details**:
- Module `app/core/middleware.py`:
  - Function `setup_exception_handlers(app: FastAPI)`:
    - app.exception_handler(AppException)(handle_app_exception):
      - Return JSONResponse(status_code=exc.status_code, content=exc.to_response())
    - app.exception_handler(RequestValidationError)(handle_validation_error):
      - Return JSONResponse(status_code=422, content={error_code: "VALIDATION_ERROR", details: exc.errors()})
    - app.exception_handler(Exception)(handle_generic_exception):
      - Log full traceback
      - Return JSONResponse(status_code=500, content={error_code: "INTERNAL_SERVER_ERROR", message: "An unexpected error occurred"})
  - Function `setup_logging_middleware(app: FastAPI)`:
    - @app.middleware("http")
    - async middleware(request: Request, call_next):
      - Generate request_id = uuid4()
      - Log: method, path, query_params
      - Start timer
      - response = await call_next(request)
      - Log: status_code, duration, response.headers
      - response.headers["X-Request-ID"] = str(request_id)
      - return response

---

### Task 5.16: Add OpenAPI/Swagger Documentation
**Spec Requirement**: API documentation via Swagger UI  
**Depends On**: Task 5.12  
**Delivery**: Swagger/Scalar configuration in app/main.py  
**Verification**:
```bash
curl http://localhost:8000/api/docs 2>/dev/null | grep -i openapi
# Should return HTML with OpenAPI spec
```

**Details**:
- In app/main.py:
  - app.openapi_schema: auto-generated from routes
  - app.swagger_ui_init_oauth: empty (no OAuth)
  - Include OpenAPI endpoint: GET /api/openapi.json
  - Include Swagger UI: GET /api/docs
  - Include ReDoc: GET /api/redoc
  - Use Scalar (optional): GET /api/scalar

---

## Phase 6: Tests & Finalization (6 tasks)

*Tasks can parallelize; all depend on Phase 5 completion.*

### Task 6.1: Write Unit Tests for Services
**Spec Requirement**: >75% coverage for services  
**Depends On**: Task 5.2, pytest setup from Task 1.2  
**Delivery**: `tests/unit/test_merchant_service.py`, `tests/unit/test_mcc_service.py`, `tests/unit/test_external_merchant_service.py`  
**Verification**:
```bash
cd payments-mcc-classification && pytest tests/unit/ --cov=app.services --cov-report=term-missing
# Should report >75% coverage
```

**Details**:
- Test file: `tests/unit/test_merchant_service.py`:
  - Fixture: mock_llm_provider (AsyncMock of ILlmProvider)
  - Fixture: mock_session (AsyncMock of AsyncSession)
  - Fixture: merchant_service = MerchantService(mock_llm_provider)
  - Test: test_create_merchant_success
  - Test: test_create_merchant_duplicate_raises_conflict
  - Test: test_get_merchant_not_found_raises_error
  - Test: test_update_merchant_success
  - Test: test_delete_merchant_soft_deletes
  - Test: test_search_merchants_by_similarity
  - Test: test_assign_mcc_to_merchant
- Similar tests for MccService, ExternalMerchantService
- Use pytest-asyncio and AsyncMock for async functions
- Mock database operations to avoid DB dependency

---

### Task 6.2: Write Unit Tests for Pipeline Engine
**Spec Requirement**: >75% coverage for pipeline engine  
**Depends On**: Task 4.1, pytest setup  
**Delivery**: `tests/unit/test_pipeline_engine.py`  
**Verification**:
```bash
cd payments-mcc-classification && pytest tests/unit/test_pipeline_engine.py --cov=app.pipeline --cov-report=term-missing
# Should report >75% coverage
```

**Details**:
- Test file: `tests/unit/test_pipeline_engine.py`:
  - Fixture: pipeline_context = PipelineContext(...)
  - Test: test_step_registration
  - Test: test_blocking_steps_execute_sequentially
  - Test: test_non_blocking_steps_execute_concurrently
  - Test: test_should_run_skips_step
  - Test: test_step_timeout_cancels_task
  - Test: test_exception_in_blocking_step_stops_pipeline
  - Test: test_exception_in_non_blocking_step_logged_not_stopped
  - Test: test_context_data_shared_across_steps
  - Create stub test steps (TestStep1, TestStep2)
  - Use AsyncMock for async execute methods

---

### Task 6.3: Write Unit Tests for Providers
**Spec Requirement**: >75% coverage for providers  
**Depends On**: Tasks 4.2, 4.3, 4.4, pytest setup  
**Delivery**: `tests/unit/test_llm_provider.py`, `tests/unit/test_card_provider.py`, `tests/unit/test_embedding_provider.py`  
**Verification**:
```bash
cd payments-mcc-classification && pytest tests/unit/test_*_provider.py --cov=app.providers --cov-report=term-missing
# Should report >75% coverage
```

**Details**:
- Test file: `tests/unit/test_llm_provider.py`:
  - Fixture: mock_openai_client (AsyncMock)
  - Fixture: llm_provider = OpenAiProvider(api_key="test")
  - Test: test_generate_calls_openai_api
  - Test: test_embed_returns_vector
  - Test: test_research_returns_formatted_string
  - Test: test_generate_timeout_raises_error
  - Mock httpx.AsyncClient for HTTP calls
- Similar structure for CardProvider, EmbeddingProvider tests

---

### Task 6.4: Write Integration Tests (DB + Services)
**Spec Requirement**: >50% coverage for full flows  
**Depends On**: All Phase 3 tasks (DB models), all Phase 5 tasks (services)  
**Delivery**: `tests/integration/test_merchant_flow.py`, `tests/integration/test_auto_creation_flow.py`  
**Verification**:
```bash
cd payments-mcc-classification && pytest tests/integration/ --cov=app --cov-report=term-missing
# Should report >50% coverage and pass
```

**Details**:
- Fixture: async_session (real AsyncSession with rollback per test for isolation)
- Fixture: test_db (temporary PostgreSQL database for test)
- Test file: `tests/integration/test_merchant_flow.py`:
  - test_create_merchant_and_save_to_db
  - test_search_merchants_by_similarity_with_real_embeddings
  - test_assign_mcc_and_verify_relationship
  - test_soft_delete_merchant
- Test file: `tests/integration/test_auto_creation_flow.py`:
  - test_auto_creation_pipeline_creates_merchant
  - test_auto_creation_pipeline_with_google_places_enrichment
  - test_auto_creation_pipeline_on_duplicate_skips_creation
  - test_validation_pipeline_rejects_invalid_mcc
- Use docker-compose test database (or pytest PostgreSQL fixture)
- Roll back transactions per test for isolation

---

### Task 6.5: Write E2E Tests (Full API Flow)
**Spec Requirement**: >30% coverage of all API endpoints  
**Depends On**: Task 5.12 (app fully wired)  
**Delivery**: `tests/e2e/test_merchant_api.py`, `tests/e2e/test_auto_creation_api.py`  
**Verification**:
```bash
cd payments-mcc-classification && pytest tests/e2e/ --cov=app.api --cov-report=term-missing
# Should report >30% coverage and pass
```

**Details**:
- Use FastAPI TestClient (or httpx.AsyncClient)
- Fixture: app (FastAPI app from create_app())
- Fixture: client = TestClient(app)
- Test file: `tests/e2e/test_merchant_api.py`:
  - test_post_merchant_creates_and_returns_201
  - test_get_merchant_returns_200
  - test_list_merchants_returns_200
  - test_patch_merchant_updates_and_returns_200
  - test_delete_merchant_returns_204
  - test_post_bulk_merchants_creates_multiple
  - test_post_search_merchants_returns_results
  - test_missing_hmac_signature_returns_401
  - test_invalid_hmac_signature_returns_401
  - test_health_endpoint_returns_ok
- Test file: `tests/e2e/test_auto_creation_api.py`:
  - test_post_auto_create_merchant_triggers_pipeline
  - test_post_validate_merchant_returns_validation_result
- Use mock HMAC header: X-API-Signature = compute_hmac(request_body, secret)

---

### Task 6.6: Finalize README, Docker, & Delivery
**Spec Requirement**: Complete documentation, production-ready setup  
**Depends On**: All prior tasks  
**Delivery**: `README.md`, update `docker-compose.yml`, `Dockerfile`, `.gitignore`, `pyproject.toml`  
**Verification**:
```bash
cd payments-mcc-classification
docker-compose up -d
docker-compose exec web python -m pytest --cov=app
docker-compose down
# Should complete without errors
```

**Details**:

**`README.md`**:
- Title & description
- Stack: Python 3.11+, FastAPI, SQLAlchemy 2.x, pgvector, pytest
- Quick start:
  ```bash
  docker-compose up -d
  source venv/bin/activate  # or poetry shell
  pip install -e ".[dev]"
  alembic upgrade head
  uvicorn app.main:create_app --reload
  ```
- API endpoints: link to OpenAPI docs
- Testing: `pytest`, `pytest --cov=app`
- Architecture: Layers (API, Services, Pipeline, Providers, Repositories, Models)
- Key patterns:
  - @transactional decorator
  - @step decorator + PipelineEngine
  - ILlmProvider + ICardProvider abstraction
  - Async contextvars for transaction management
  - Outbox pattern for reliable event delivery
- Environment variables: link to .env.example
- Troubleshooting: common issues & solutions

**`Dockerfile`**:
- Base: python:3.11-slim
- WORKDIR /app
- COPY requirements: pyproject.toml, poetry.lock (if using Poetry)
- RUN pip install -e .
- COPY app code
- EXPOSE 8000
- CMD: ["uvicorn", "app.main:create_app()", "--host", "0.0.0.0", "--port", "8000"]

**`docker-compose.yml`** (update):
- Service `web`:
  - Image: payments-mcc-classification:latest (build from Dockerfile)
  - Ports: 8000:8000
  - Environment: DATABASE_URL, OPENAI_API_KEY, etc. (from .env)
  - Depends on: postgres, redis
  - Health check: curl http://localhost:8000/health
  - Volumes: ./app:/app (for hot reload in dev)
- Service `postgres`: already defined (Task 1.3)
- Service `redis`: already defined (Task 1.3)

**`.gitignore`**:
- __pycache__/
- *.py[cod]
- *$py.class
- .venv, venv, env
- .env, .env.local
- *.db, *.sqlite3
- .pytest_cache, .coverage, htmlcov
- .mypy_cache, .dmypy.json
- .idea/, .vscode/
- *.egg-info/
- dist/, build/

**`pyproject.toml`** (finalize):
- Ensure all scripts defined (dev, lint, format, test, test:cov, migrate, migrate:create)
- Add tool.pytest config:
  ```toml
  [tool.pytest.ini_options]
  asyncio_mode = "auto"
  testpaths = ["tests"]
  python_files = ["test_*.py", "*_test.py"]
  ```
- Add tool.coverage config:
  ```toml
  [tool.coverage.run]
  source = ["app"]
  omit = ["*/tests/*", "*/__init__.py"]
  [tool.coverage.report]
  exclude_lines = ["pragma: no cover", "def __repr__", "raise NotImplementedError"]
  ```
- Add tool.mypy config:
  ```toml
  [tool.mypy]
  python_version = "3.11"
  warn_return_any = true
  warn_unused_configs = true
  disallow_untyped_defs = false
  ```

---

## Summary Table

| Phase | Tasks | Sequential | Parallel | Est. Time |
|-------|-------|-----------|----------|-----------|
| 1. Bootstrap | 4 | 4 | 0 | 1 day |
| 2. Infrastructure | 5 | 0 | 5 | 1 day |
| 3. Data Layer | 7 | 2 | 5 | 2 days |
| 4. Engine & Providers | 9 | 1 | 8 | 2 days |
| 5. API & Workers | 16 | 2 | 14 | 4 days |
| 6. Tests & Finalization | 6 | 0 | 6 | 2 days |
| **TOTAL** | **47** | 9 | 38 | **12 days** |

---

## Risk Assessment

1. **Transaction Context (Task 2.2)**: ContextVar[AsyncSession] is critical. If not wired correctly, nested calls will create independent transactions, breaking isolation. Mitigation: Test nested service calls with transaction rollback.

2. **pgvector Index Performance (Task 3.7)**: ivfflat index on Vector(1536) columns can be slow for large datasets (>100k merchants). Mitigation: Add monitoring; use reasonable LIMIT in queries.

3. **Outbox Polling Scalability (Task 5.13)**: 2-second polling interval may miss events if worker is slow. Mitigation: Implement exponential backoff; monitor event latency; consider Redis-backed queue in future.

4. **LangFuse Optional (Task 4.2)**: If LangFuse URL unreachable, traces fail. Mitigation: Wrap in try/except, graceful fallback to no-op handler.

5. **External Provider Integration (Tasks 4.2, 4.3)**: OpenAI/Pomelo API keys required for full functionality. Mitigation: Mock providers for tests; support optional providers with feature flags.

---

## Review Workload Forecast (Detailed)

| Category | Lines | Notes |
|----------|-------|-------|
| Models + Migrations | 1,200 | 9 entities + relationships + constraints |
| Services (core + pipeline steps) | 2,500 | 3 services × ~400 LOC + 7 steps × ~100 LOC |
| Repositories | 1,000 | 7 repo classes × ~140 LOC |
| Providers | 1,200 | LLM (200) + Card (200) + Embedding (150) + Google (100) + S3 (100) + SNS (100) + base (250) |
| API Routers | 2,200 | 7 routers × ~300 LOC (endpoints + exception handling) |
| Schemas (Pydantic) | 600 | 15+ DTO classes |
| Core Infrastructure | 800 | config (150) + context (150) + exceptions (100) + auth (150) + database (100) + dependencies (150) |
| Workers | 400 | Outbox processor (200) + lifecycle (100) + middleware (100) |
| Tests | 2,000 | Unit (1,000) + Integration (600) + E2E (400) |
| Docker + Config | 500 | Dockerfile, docker-compose, .env, README |
| **GRAND TOTAL** | **12,000** | Estimated range: 10,500–13,500 LOC |

**Chained PRs Recommended: YES**
- PR1: Bootstrap + Infrastructure (Day 1–2, ~800 LOC)
- PR2: Data Layer + Migrations (Day 2–3, ~1,500 LOC)
- PR3: Engine + Providers (Day 3–4, ~2,800 LOC)
- PR4: API Routers + Schemas (Day 4–6, ~3,000 LOC)
- PR5: Workers + Outbox (Day 6–7, ~800 LOC)
- PR6: Tests + Finalization (Day 7–9, ~2,000 LOC)

**Decision Needed Before Apply**: 
- Confirm Python version (3.11 vs 3.12 vs 3.13)
- Confirm PostgreSQL version (14 vs 15 vs 16)
- Confirm LangFuse integration (mandatory vs optional)
- Confirm whether to use Poetry or pip for dependency management
- Confirm Redis requirement (optional in v1, mandatory in v2)

---
