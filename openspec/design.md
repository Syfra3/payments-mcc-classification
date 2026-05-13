# Design: payments-classification-mcp

## Technical Approach

**Layered async Python FastAPI service** porting the NestJS glim-merchant-microservice with architectural parity. The design preserves the original's patterns (pipeline engine, provider abstraction, transaction management, outbox pattern) while adapting for Python's async/await ecosystem. Context management via `contextvars` replaces NestJS's AsyncLocalStorage. SQLAlchemy 2.x async ORM with pgvector embeddings maintains the database strategy. Step-based pipeline engine with decorator-driven discovery mirrors the NestJS BaseEngineService.

## Architecture Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| **Transaction Context** | `contextvars.ContextVar[AsyncSession]` per request | Python's stdlib equivalent to NestJS's AsyncLocalStorage. Cleaner, zero-dependency approach. `@transactional` decorator stores/retrieves ambient session. |
| **ORM & Async** | SQLAlchemy 2.x + asyncpg | SQLAlchemy v2 has first-class async support. asyncpg is the fastest PostgreSQL driver. Both are production-ready. Alembic for migrations. |
| **Pipeline Engine** | Decorator-driven class registry | Steps decorated with `@step(registry, order, execution_type, timeout)`. Engine discovers steps via module imports. Mirrors NestJS reflection pattern. Supports blocking (transaction-participating) and non-blocking (fire-and-forget) execution. |
| **LLM Provider** | Interface + default (OpenAI) | `ILlmProvider` ABC defines `generate()`, `embed()` contracts. OpenAI as default. Swappable without touching pipeline logic. Consumers depend on the interface, not the implementation. |
| **Card Provider** | Interface + default (Pomelo) | `ICardProvider` ABC defines `normalize_merchant()`, `get_transactions()`, `lookup()` contracts. Pomelo as default. DI container selects implementation per environment. |
| **Embedding Storage** | pgvector on Merchant/Mcc + Embedding table | Vector columns `embedding: Vector(1536)` on Merchant, `embedding: Vector(768)` on Mcc. Separate `Embedding` table for metadata and link tracking. `pgvector` index: `btree_gin` for filtering, `ivfflat` for similarity. |
| **Soft Deletes** | SQLAlchemy hybrid_property `is_deleted` | `deleted_at: DateTime | None`. Hybrid property `is_deleted` for filter clarity. All queries filter `deleted_at IS NULL` by default. Works with eager/lazy loading. |
| **Outbox Worker** | Async polling loop + background task | `AsyncOutboxProcessor` polls every 2s, retries with exponential backoff (1s → 32s). Uses asyncio.gather for concurrent event processing (max 5 concurrent). Marks complete/failed/dead-letter. No Redis required (v1). |
| **Request Authentication** | HMAC guard + JWT fallback | Replicates `GlimHmacGuard` from @glim-it. HMAC signature in `X-Glim-Signature` header verified via shared secret. JWT fallback for internal requests. Unprotected health check. |
| **API Versioning** | URI prefix `/api/v1/` | FastAPI router includes with `prefix="/v1"`. Mirrors NestJS @Version('1') behavior. Easy multi-version support later. |
| **Logging & Traces** | LangFuse + structlog | LangFuse callback handler wired to LangChain chains for LLM pipeline steps. structlog for structured JSON logs. Langfuse optional (graceful fallback if unavailable). |
| **Config Management** | Pydantic Settings from env | `Settings(BaseSettings)` with validators. Type-safe, env-var auto-loading, `.env` support. Validates required vars at startup (PORT, DB_URL, OPENAI_API_KEY, etc.). |
| **Error Handling** | Exception filters + middleware | `@app.exception_handler(ValidationError)` returns 422. Custom exceptions map to HTTP status codes. Logging middleware captures request/response. |
| **Testing** | pytest-asyncio + fixtures | Async test support. Fixture-based database (transaction rollback per test for isolation). Mock providers via httpx. >75% coverage for services/models/engine; <50% for routers (acceptable). |

## Data Flow

### Request → Service → Pipeline → Providers → Database

```
FastAPI Router (async handler)
    ↓
@transactional decorator (gets/creates ambient session)
    ↓
MerchantService (stateless, business logic)
    ↓
PipelineEngine.run("registry_name", context)
    ↓ (blocking steps execute sequential)
BaseStep.execute(context) ← accesses ambient session via context
    ↓ (call provider)
ILlmProvider.generate() / ICardProvider.lookup()
    ↓
Repository (pulls ambient session from contextvars)
    ↓
SQLAlchemy async ORM ← executes in ambient transaction
    ↓
PostgreSQL + pgvector
    ↓ (save to Outbox in same transaction)
OutboxEvent stored
    ↓ (commit on decorator exit)
AsyncOutboxProcessor polls table
    ↓
Call downstream service (Voucher API)
    ↓
Mark Outbox event as delivered/failed
```

### Entity Relationships

```
Merchant (PK: id UUID)
  ├─ one-to-many → ExternalMerchant (PK: provider, external_id)
  ├─ many-to-many → Mcc (via MerchantMcc join table)
  ├─ one-to-one → MerchantMetadata (PK: merchant_id)
  └─ one-to-many → Embedding (merchant_id, type)

Mcc (PK: id UUID)
  ├─ many-to-one → Category (category_id)
  └─ one-to-many → Embedding (mcc_id, type)

Outbox (PK: id UUID)
  └─ JSON payload → references aggregate (merchant_id, mcc_id, etc.)

FailedMerchantCreation (PK: id UUID)
  └─ tracks creation attempts (external_merchant_id, retry_count, error)
```

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `app/main.py` | Create | FastAPI app, router registration, middleware, exception handlers, startup/shutdown |
| `app/api/routes/merchant.py` | Create | FastAPI router: GET, POST, PUT, DELETE, bulk ops, provider lookups |
| `app/api/routes/mcc.py` | Create | FastAPI router: GET, POST, PUT, list MCCs, similarity search |
| `app/api/routes/health.py` | Create | Health check endpoint (no auth) |
| `app/api/schemas.py` | Create | Pydantic v2 request/response schemas, OpenAPI decorators |
| `app/api/guards.py` | Create | HMAC guard, JWT extraction, dependency injection |
| `app/services/merchant.py` | Create | MerchantService: CRUD, engine orchestration, transaction boundary |
| `app/services/mcc.py` | Create | MccService: CRUD, embedding operations |
| `app/services/external_merchant.py` | Create | ExternalMerchantService: provider mapping, deduplication |
| `app/pipeline/engine.py` | Create | BaseStep ABC, PipelineEngine, step registry, execution logic |
| `app/pipeline/decorators.py` | Create | @step() decorator, StepMeta dataclass, registry enum |
| `app/pipeline/steps/__init__.py` | Create | Auto-discover and register steps (import * triggers __init_subclass__) |
| `app/pipeline/steps/auto_creation.py` | Create | Steps: check_existence, research, embed, register_merchant |
| `app/pipeline/steps/validation.py` | Create | Steps: find_by_name, check_dedup, create_draft, associate |
| `app/providers/llm.py` | Create | ILlmProvider interface, OpenAI implementation, LangChain integration |
| `app/providers/card.py` | Create | ICardProvider interface, Pomelo implementation |
| `app/providers/google_place.py` | Create | Google Places API client (stub for v1) |
| `app/repositories/base.py` | Create | BaseRepository: session context, async queries, soft-delete filter |
| `app/repositories/merchant.py` | Create | MerchantRepository: find, create, embed, similarity_search |
| `app/repositories/mcc.py` | Create | MccRepository: find, upsert, embed |
| `app/repositories/outbox.py` | Create | OutboxRepository: save, poll, mark_done, mark_failed |
| `app/models.py` | Create | SQLAlchemy 2.x models: Merchant, ExternalMerchant, Mcc, MerchantMetadata, Outbox, FailedMerchantCreation, Embedding, Category, MerchantMcc |
| `app/core/context.py` | Create | `transactional` decorator, session ContextVar, request-scoped session factory |
| `app/core/config.py` | Create | Pydantic Settings: validate PORT, DB_URL, OPENAI_API_KEY, ENVIRONMENT, etc. |
| `app/core/database.py` | Create | async_engine, AsyncSession factory, event listeners, startup/shutdown |
| `app/core/exceptions.py` | Create | Custom exceptions (ValidationError, DuplicateError, NotFoundError, etc.) |
| `app/core/dependencies.py` | Create | Dependency injection: providers, repositories, services |
| `app/workers/outbox.py` | Create | AsyncOutboxProcessor: poll loop, retry logic, event handler callback |
| `alembic/env.py` | Create | Alembic config for async migrations |
| `alembic/versions/0001_initial_schema.py` | Create | Create all 9 tables, indexes, pgvector extension |
| `alembic/versions/0002_pgvector_extension.py` | Create | Install pgvector extension if not already present |
| `tests/conftest.py` | Create | pytest-asyncio fixtures: async client, test db, session, provider mocks |
| `tests/unit/test_models.py` | Create | SQLAlchemy model instantiation, relationships, soft-delete logic |
| `tests/unit/test_services.py` | Create | MerchantService, MccService, ExternalMerchantService (mocked repos) |
| `tests/unit/test_pipeline.py` | Create | BaseStep execution, PipelineEngine registry, blocking/non-blocking logic |
| `tests/unit/test_providers.py` | Create | LLM provider interface, mock implementations |
| `tests/integration/test_merchant_api.py` | Create | Full create-merchant flow, transaction rollback, outbox save |
| `tests/integration/test_mcc_api.py` | Create | MCC CRUD, embedding similarity search |
| `tests/integration/test_outbox_worker.py` | Create | Outbox event polling, retry, downstream call mock |
| `docker-compose.yml` | Create | PostgreSQL 15+pgvector, Redis (optional), Adminer, app service |
| `pyproject.toml` | Create | Dependencies, build config, pytest settings |
| `Dockerfile` | Create | Multi-stage: builder, runtime; Python 3.11 slim base |
| `.env.example` | Create | Template: PORT, DB_URL, OPENAI_API_KEY, ENVIRONMENT |
| `README.md` | Create | Setup, commands (poetry install, alembic upgrade, pytest), architecture overview |

## Interfaces / Contracts

### Transaction Decorator

```python
from contextvars import ContextVar
from typing import Any, Callable, TypeVar
from functools import wraps
from sqlalchemy.ext.asyncio import AsyncSession

_session_context: ContextVar[AsyncSession | None] = ContextVar(
    "session", default=None
)

def transactional(force_new: bool = False):
    """Ambient transaction decorator. Stores/retrieves session via contextvars."""
    def decorator(fn: Callable) -> Callable:
        @wraps(fn)
        async def wrapper(*args, **kwargs):
            existing = _session_context.get()
            if existing and not force_new:
                # Reuse ambient session
                return await fn(*args, **kwargs)
            # Create new transaction
            async with get_async_session() as session:
                token = _session_context.set(session)
                try:
                    result = await fn(*args, **kwargs)
                    await session.commit()
                    return result
                except Exception:
                    await session.rollback()
                    raise
                finally:
                    _session_context.reset(token)
        return wrapper
    return decorator
```

### Pipeline Step Interface

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict

class ExecutionType(str, Enum):
    BLOCKING = "blocking"
    NON_BLOCKING = "non_blocking"

@dataclass
class StepMeta:
    registry: str
    order: int
    execution_type: ExecutionType = ExecutionType.BLOCKING
    timeout: float | None = None

def step(
    registry: str,
    order: int,
    execution_type: ExecutionType = ExecutionType.BLOCKING,
    timeout: float | None = None,
):
    """Decorator to register a step in a pipeline."""
    def decorator(cls):
        cls._step_meta = StepMeta(registry, order, execution_type, timeout)
        # Auto-register in global registry
        STEP_REGISTRY.setdefault(registry, []).append(cls)
        return cls
    return decorator

class BaseStep(ABC):
    """Base class for pipeline steps."""
    _step_meta: StepMeta

    async def should_run(self, context: Dict[str, Any]) -> bool:
        """Override to conditionally skip this step."""
        return True

    @abstractmethod
    async def execute(self, context: Dict[str, Any]) -> None:
        """Execute the step. Modify context in-place."""
        pass

class PipelineEngine:
    async def run(
        self,
        registry: str,
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Run all steps in a registry. Blocking steps execute sequentially."""
        steps = sorted(
            STEP_REGISTRY.get(registry, []),
            key=lambda s: s._step_meta.order,
        )
        results = {"context": context, "executed": [], "failed": []}
        for step_cls in steps:
            step = step_cls()
            if not await step.should_run(context):
                continue
            try:
                await asyncio.wait_for(
                    step.execute(context),
                    timeout=step._step_meta.timeout or None,
                )
                results["executed"].append(step_cls.__name__)
            except Exception as e:
                results["failed"].append((step_cls.__name__, str(e)))
                if step._step_meta.execution_type == ExecutionType.BLOCKING:
                    raise  # Blocking steps fail the pipeline
        return results
```

### LLM Provider Interface

```python
from abc import ABC, abstractmethod

class ILlmProvider(ABC):
    @abstractmethod
    async def generate(
        self,
        prompt: str,
        model: str = "gpt-4",
        temperature: float = 0.7,
        max_tokens: int = 2000,
    ) -> str:
        """Generate text from a prompt."""
        pass

    @abstractmethod
    async def embed(self, text: str) -> list[float]:
        """Embed text to a vector."""
        pass

class OpenAIProvider(ILlmProvider):
    def __init__(self, api_key: str):
        self.client = AsyncOpenAI(api_key=api_key)

    async def generate(self, prompt: str, **kwargs) -> str:
        response = await self.client.chat.completions.create(
            model=kwargs.get("model", "gpt-4"),
            messages=[{"role": "user", "content": prompt}],
            temperature=kwargs.get("temperature", 0.7),
            max_tokens=kwargs.get("max_tokens", 2000),
        )
        return response.choices[0].message.content

    async def embed(self, text: str) -> list[float]:
        response = await self.client.embeddings.create(
            model="text-embedding-3-small",
            input=text,
        )
        return response.data[0].embedding
```

### Card Provider Interface

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass

@dataclass
class ExternalMerchantDTO:
    provider: str
    external_id: str
    name: str
    mcc: str | None
    metadata: dict

class ICardProvider(ABC):
    @abstractmethod
    async def lookup_merchant(
        self,
        provider_id: str,
        external_id: str,
    ) -> ExternalMerchantDTO | None:
        """Lookup a merchant from the provider."""
        pass

    @abstractmethod
    async def get_transactions(self, filters: dict) -> list[dict]:
        """Get transactions matching filters."""
        pass

class PomeloProvider(ICardProvider):
    def __init__(self, api_key: str, api_url: str):
        self.client = httpx.AsyncClient(
            headers={"Authorization": f"Bearer {api_key}"},
            base_url=api_url,
        )

    async def lookup_merchant(
        self,
        provider_id: str,
        external_id: str,
    ) -> ExternalMerchantDTO | None:
        response = await self.client.get(
            f"/merchants/{external_id}",
            params={"provider_id": provider_id},
        )
        if response.status_code == 200:
            data = response.json()
            return ExternalMerchantDTO(
                provider=provider_id,
                external_id=external_id,
                name=data.get("name"),
                mcc=data.get("mcc"),
                metadata=data,
            )
        return None
```

### SQLAlchemy Models (Excerpt)

```python
from sqlalchemy import Column, String, DateTime, Text, Float, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import DeclarativeBase, relationship
from pgvector.sqlalchemy import Vector
from datetime import datetime
import uuid

class Base(DeclarativeBase):
    pass

class Merchant(Base):
    __tablename__ = "merchants"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), unique=True, nullable=False, index=True)
    mcc_primary = Column(String(4), nullable=True)
    embedding = Column(Vector(1536), nullable=True)
    logo_url = Column(String(512), nullable=True)
    weight = Column(Float, default=1.0)
    metadata_json = Column(JSONB, default={})
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    deleted_at = Column(DateTime, nullable=True)
    
    external_merchants = relationship("ExternalMerchant", back_populates="merchant")
    mccs = relationship("Mcc", secondary="merchant_mccs", back_populates="merchants")
    metadata = relationship("MerchantMetadata", uselist=False, back_populates="merchant")
    
    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None

class ExternalMerchant(Base):
    __tablename__ = "external_merchants"
    __table_args__ = (
        Index("ix_external_merchant_provider_id", "provider", "external_id", unique=True),
    )
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    provider = Column(String(50), nullable=False)
    external_id = Column(String(255), nullable=False)
    merchant_id = Column(UUID(as_uuid=True), ForeignKey("merchants.id"), nullable=True)
    raw_data = Column(JSONB, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    deleted_at = Column(DateTime, nullable=True)
    
    merchant = relationship("Merchant", back_populates="external_merchants")

class Outbox(Base):
    __tablename__ = "outbox"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    aggregate_id = Column(UUID(as_uuid=True), nullable=False)
    event_type = Column(String(100), nullable=False)
    payload = Column(JSONB, nullable=False)
    status = Column(String(50), default="pending")  # pending, delivered, failed, dead_letter
    attempts = Column(Integer, default=0)
    last_error = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (
        Index("ix_outbox_status_created", "status", "created_at"),
    )
```

## Testing Strategy

| Layer | What to Test | Approach |
|-------|-------------|----------|
| Unit | Model instantiation, relationships, soft-delete hybrid property | Synchronous SQLAlchemy model tests; no DB required |
| Unit | Service orchestration (MerchantService calls repos, pipeline) | Mock repositories, providers; async test functions |
| Unit | Pipeline engine: step registry, blocking vs non-blocking, shouldRun(), timeout | Mock steps that raise/succeed; verify execution order and results |
| Unit | Provider interfaces: OpenAI embed/generate, Pomelo lookup | Mock httpx responses; verify payload format |
| Integration | Full create-merchant flow: API → Service → Pipeline → Repo → DB | Async test DB (transaction rollback per test); pytest fixtures |
| Integration | Transaction ambient session: nested calls see same session | Verify contextvars isolation per test; concurrent tests don't interfere |
| Integration | Outbox polling, event delivery, retry backoff | Mock downstream service; verify Outbox status transitions |
| E2E | API contract: POST /merchants, GET /merchants/{id}, DELETE /merchants/{id} | FastAPI test client; real async DB; Docker Compose for CI |

Test database strategy: `async_session_maker(expire_on_commit=False)` + transaction rollback per test for isolation. No cleanup needed.

## Migration / Rollout

**Dual-write phase** (2 weeks):
1. Deploy Python service alongside NestJS.
2. All writes go to both services (middleware routes POST/PUT/DELETE to both).
3. Reads come from NestJS only (feature flag gates Python reads).
4. Verify data consistency daily.

**Read traffic migration** (1 week):
1. Enable Python reads for GET /merchants via feature flag (5% traffic).
2. Compare response times and error rates.
3. Gradually increase to 100%.

**Deprecation** (30 days post-launch):
1. Keep NestJS running; async replication can catch up.
2. Monitor Outbox delivery to Voucher service (verify no message loss).
3. After 30 days with zero issues, retire NestJS service.

**Database**: PostgreSQL migrations are reversible (Alembic tracks state). Keep NestJS schema in sync during dual-write phase.

**Rollback trigger**: If Python service error rate exceeds 5% or latency increases >2x, switch all traffic back to NestJS immediately.

## Open Questions

- [ ] How to obtain the Python equivalent of `@glim-it/glim-common-api` HMAC guard? (Stub implementation provided; verify integration path)
- [ ] Should LangFuse tracing be mandatory or optional in v1? (Currently optional; graceful fallback)
- [ ] Confirm ExternalMerchant → Merchant field mapping with Pomelo schema documentation
- [ ] Should Redis be required for Outbox distributed locking, or is single-instance polling sufficient for v1? (Currently polling-only; Redis deferred)
- [ ] Approval for 800-line design document word budget (current: ~750 words, includes code sketches)
