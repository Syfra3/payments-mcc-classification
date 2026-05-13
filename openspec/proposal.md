# Proposal: payments-classification-mcp

## Intent

Port the glim-merchant-microservice (NestJS/TypeScript) to Python with FastAPI, creating a vendor-neutral, cloud-native payments classification service. This service will manage merchant data, embeddings, and intelligent classification pipelines using multiple AI and payment provider backends. The primary driver is **technology stack diversification** — enabling Python teams to collaborate on the payments domain while maintaining architectural parity with the original NestJS implementation.

## Scope

### In Scope
- **Core domain model** (9 entities): Merchant, ExternalMerchant, Mcc, Embedding, Outbox, MerchantMetadata, Category, MerchantMcc, FailedMerchantCreation
- **API surface** (v1): 14 merchant endpoints, 5 MCC endpoints, health check (all URI-versioned, HMAC-protected)
- **Pipeline engine**: Python equivalent of BaseEngineService/BaseEngineStep with decorator support, blocking/non-blocking steps, shouldRun(), timeout handling
- **LLM provider abstraction**: OpenAI (default) + pluggable interface for Anthropic, Gemini, etc.
- **Card/transaction provider abstraction**: Pomelo (default) + pluggable interface for Visa, Mastercard, etc.
- **Auto-creation pipeline**: CheckExistence → GooglePlace/LLM research → Embeddings → MCC fallback → Register → HumanReview + FinalRegister
- **Validation engine**: validation-before-creation pipeline
- **Database layer**: SQLAlchemy 2.x async ORM, Alembic migrations, pgvector integration
- **Transaction management**: contextvars + SQLAlchemy session scoping for ambient transactions (replaces AsyncLocalStorage)
- **Outbox pattern**: reliable event delivery to downstream services (Voucher, etc.)
- **Docker Compose**: PostgreSQL (pgvector), Redis (optional), Adminer, app service for local development
- **Testing**: pytest-asyncio, fixture-based test database, unit + integration tests

### Out of Scope
- **Multi-tenancy**: v1.0 is single-tenant; multitenancy deferred to v2
- **Event sourcing**: outbox only; full ES deferred
- **GraphQL**: REST API only in v1
- **Real-time WebSocket support**: HTTP polling/webhooks only
- **Langfuse observability**: integrated in design but traces are fire-and-forget; no custom dashboard in v1
- **OAuth/custom auth**: HMAC + JWT only (HMAC from global @glim-it/glim-common-api equivalent TBD)
- **Blue-green deployment**: standard containerization; advanced deployment strategies deferred
- **DynamoDB integration**: PostgreSQL only in v1; DynamoDB deferred to v2
- **SNS event publishing**: webhook callbacks only in v1; SNS integration deferred

## Capabilities

### New Capabilities
- `fastapi-merchant-api`: REST endpoints for merchant CRUD, bulk operations, and provider-based management
- `embedding-similarity-search`: Vector similarity queries for merchants and MCCs using pgvector
- `pipeline-engine`: Pluggable step-based pipeline framework with blocking/non-blocking execution
- `llm-provider-abstraction`: Swappable LLM backends (OpenAI, Anthropic, Gemini) without touching pipeline logic
- `transaction-management`: Ambient transaction context via contextvars for SQLAlchemy
- `auto-creation-pipeline`: AI-driven merchant discovery and registration with research, embedding, and MCC classification
- `validation-pipeline`: Pre-creation merchant validation with provider lookup and deduplication
- `outbox-event-delivery`: Transactional outbox for reliable downstream service integration
- `mcc-classification`: Merchant category code management with embeddings and similarity search

### Modified Capabilities
- None (this is a new service; no existing capabilities to modify)

## Approach

**Layered architecture** with clear separation of concerns:

1. **API Layer** (controllers)
   - FastAPI routers with dependency injection
   - Request/response schemas via Pydantic v2
   - HMAC + JWT guards (inherited from @glim-it)
   - Swagger/OpenAPI via FastAPI native support

2. **Service Layer** (domain orchestration)
   - MerchantService, MccService, ExternalMerchantService
   - Engine factory for pipeline instantiation
   - Stateless, business logic only

3. **Pipeline Engine** (BaseEngineService equivalent)
   - Step registry (in-memory, decorator-driven discovery)
   - Blocking vs non-blocking execution
   - shouldRun() conditional logic
   - Timeout handling per step
   - LangFuse trace injection
   - Composed pipeline templates (AutoCreation, Validation)

4. **Provider Abstraction** (swappable backends)
   - `ILlmProvider` interface: implement(text, model, temperature, etc.)
   - `ICardProvider` interface: lookup_merchant(provider_id, external_id), etc.
   - OpenAI + Pomelo as default implementations
   - DI container registers implementations per environment

5. **Database Layer** (SQLAlchemy + Alembic)
   - Async models with UUID v5 for Merchant PK (deterministic)
   - pgvector for embeddings (768-dim)
   - Soft deletes via SQLAlchemy hybrid_property
   - QueryRunner equivalent via contextvars + session scoping

6. **Transaction Management** (contextvars-based)
   - `@transactional` decorator on service methods
   - Stores SQLAlchemy session in contextvars.ContextVar
   - Nested transaction support via savepoints
   - Repositories pull session via context lookup

7. **Event Outbox** (AsyncOutboxProcessor)
   - Saves events in same transaction as business operation
   - Background worker polls outbox table
   - Retries with exponential backoff
   - Marks events as delivered when downstream ACKs

**Migration Path**: None → new Python codebase. Initial data seeding can come from NestJS exports.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `src/api/` | New | FastAPI routers for merchants, MCCs, health |
| `src/services/` | New | Domain service orchestration layer |
| `src/pipeline/` | New | BaseEngineService + Step framework (Python equivalent) |
| `src/providers/llm/` | New | LLM provider abstraction + OpenAI implementation |
| `src/providers/card/` | New | Card/transaction provider abstraction + Pomelo implementation |
| `src/models/` | New | SQLAlchemy ORM models (9 entities) |
| `src/migrations/` | New | Alembic migration scripts |
| `src/database/` | New | Connection, session management, transaction context |
| `tests/` | New | pytest-asyncio unit + integration tests |
| `docker-compose.yml` | New | PostgreSQL, Redis, Adminer, app service |
| `pyproject.toml` | New | Dependencies, tooling (FastAPI, SQLAlchemy, Pydantic, httpx, LangChain, etc.) |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| **Async context propagation bugs** | High | Extensive testing of nested transactions, savepoints, and error rollback; use pytest fixtures to verify contextvars isolation per test |
| **pgvector performance** | Medium | Pre-index similarity queries, set work_mem appropriately, benchmark with realistic dataset sizes early |
| **LLM provider swapping complexity** | Medium | Define ILlmProvider interface early, mock all providers in tests, document interface contract clearly |
| **Event delivery guarantees** | Medium | Implement idempotency keys, test Outbox worker under network failures and DB downtime, add alerting for stuck events |
| **Docker Compose tooling drift** | Low | Pin all service image versions (PostgreSQL 15.x, Redis 7.x), document init scripts, validate with CI |
| **Missing Pomelo field mappings** | Medium | Document all ExternalMerchant → Merchant mapping rules before auto-creation; validate against Pomelo schema |
| **Schema migration reversibility** | Low | Always test rollback on each Alembic migration; require downgrade scripts for production |

## Rollback Plan

1. **Before v1 launch**: Keep NestJS service running in parallel; route traffic via canary (5% Python, 95% NestJS) for 2 weeks
2. **Data**: All writes go to both services initially (dual-write pattern); on success, switch read traffic to Python
3. **Rollback**: If Python service fails, switch all traffic back to NestJS; keep Python running for async data sync catch-up
4. **Database**: Keep NestJS migrations and schemas in sync; do NOT delete or deprecate NestJS tables for 30 days post-launch
5. **Config**: Feature flags control which provider implementation is active (can switch LLM/Card providers at runtime)

## Dependencies

### External Services
- PostgreSQL 15+ (pgvector extension)
- Redis 7+ (optional, for Outbox distributed locking)
- OpenAI API (default LLM provider; can swap)
- Google Places API (merchant lookup)
- Tavily API (web research)
- Pomelo API (card/transaction provider; can swap)

### Python Stack
- `fastapi` 0.104+ (web framework)
- `uvicorn` 0.24+ (ASGI server)
- `sqlalchemy` 2.0+ (async ORM)
- `asyncpg` 0.29+ (async PostgreSQL driver)
- `pgvector` 0.2+ (vector queries)
- `alembic` 1.13+ (migrations)
- `pydantic` 2.5+ (validation, serialization)
- `langchain` 0.1+ (LLM orchestration)
- `langfuse` 0.7+ (trace logging)
- `httpx` 0.25+ (async HTTP client)
- `python-dotenv` 1.0+ (config)
- `pytest` 7.4+, `pytest-asyncio` 0.21+ (testing)
- `pytest-httpx` 0.21+ (mock HTTP)

### Internal Dependencies
- `@glim-it/glim-common-api` equivalent for Python (TBD) — HMAC/JWT guards

## Success Criteria

- [ ] All 9 entities modeled in SQLAlchemy with correct relationships and constraints
- [ ] All 19 API endpoints implemented and passing integration tests (OpenAPI schema valid)
- [ ] Pipeline engine supports ≥10 concurrent steps, shouldRun() logic, and timeout handling
- [ ] LLM provider interface allows swapping OpenAI ↔ Anthropic without code changes
- [ ] Card provider interface allows swapping Pomelo ↔ test provider without code changes
- [ ] Transaction decorator ensures ambient session isolation across async tasks
- [ ] Auto-creation and Validation pipelines execute end-to-end with realistic data
- [ ] Outbox worker retries failed events and marks success; can survive 1-hour DB downtime
- [ ] Docker Compose brings up all services with `docker-compose up`; app connects to DB on first request
- [ ] Test coverage ≥75% for services, models, and pipeline engine; <50% for HTTP layer (routers) acceptable
- [ ] Feature flag system allows switching providers and pipeline behavior at runtime without restart
