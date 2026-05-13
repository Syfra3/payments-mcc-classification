# Specification: payments-classification-mcp

**Change**: payments-classification-mcp  
**Version**: 1.0  
**Status**: Spec Draft  
**Date**: 2026-05-13  
**Scope**: Python/FastAPI port of glim-merchant-microservice with plugin-based provider architecture

## Executive Summary

This specification defines the **payments-classification-mcp** service: a Python/FastAPI microservice for managing merchant data, embeddings, and AI-driven classification pipelines. The service maintains architectural parity with the original NestJS implementation while enabling Python-based teams to contribute to the payments domain. Key differentiators: pluggable LLM and card provider backends, async-native design using SQLAlchemy 2.x, and a step-based pipeline engine framework.

---

## Delta: What MUST Be True After Implementation

### Domain Model
- [ ] **9 entities** fully modeled in SQLAlchemy with async relationships:
  - `Merchant` (name UPPERCASE, embedding, metadata, weight)
  - `ExternalMerchant` (composite PK: provider+id, soft-deleted)
  - `Mcc` (industry codes with embedding, category)
  - `MerchantMcc` (join table, many-to-many)
  - `MerchantMetadata` (flags: human_created, human_modified, mcc_type, voucher_type)
  - `Category` (unique name, grouping MCCs)
  - `Embedding` (vector storage for similarity search)
  - `Outbox` (event delivery, status, retry tracking)
  - `FailedMerchantCreation` (failed attempt tracking with retry counter)

### API Surface
- [ ] **14 merchant endpoints** (v1 URI prefix):
  - POST /v1/merchants (create)
  - GET /v1/merchants (list with pagination)
  - GET /v1/merchants/{id} (retrieve)
  - PUT /v1/merchants/{id} (update)
  - DELETE /v1/merchants/{id} (soft-delete)
  - POST /v1/merchants/search/similarity (vector search)
  - POST /v1/merchants/bulk/create (batch creation)
  - POST /v1/merchants/bulk/update (batch update)
  - POST /v1/merchants/providers/{provider}/lookup (external provider lookup)
  - POST /v1/merchants/providers/{provider}/create (provider-driven creation)
  - GET /v1/merchants/{id}/metadata (metadata retrieval)
  - PATCH /v1/merchants/{id}/metadata (metadata update)
  - POST /v1/merchants/{id}/embeddings/regenerate (force embedding update)
  - GET /v1/merchants/export (export merchant data)

- [ ] **5 MCC endpoints**:
  - POST /v1/mccs (create)
  - GET /v1/mccs (list)
  - GET /v1/mccs/{id} (retrieve)
  - PUT /v1/mccs/{id} (update)
  - POST /v1/mccs/search/similarity (vector search)

- [ ] **1 health endpoint**:
  - GET /health (database + dependencies check)

- [ ] **All endpoints require HMAC authentication** (except /health)
- [ ] **All endpoints return 20x on success, 4xx on validation, 5xx on server error**
- [ ] **All responses follow OpenAPI 3.1 schema**
- [ ] **Swagger documentation auto-generated from Pydantic schemas**

### Provider Abstraction
- [ ] **ILlmProvider interface** defines contract:
  - `generate(prompt, model, temperature, max_tokens)` → str
  - `embed(text, model)` → List[float]
  - `research(query, max_results)` → List[Dict]
  - Methods must support async and sync (wrapper for batch operations)

- [ ] **OpenAI implementation** (default):
  - Uses `gpt-4`, `gpt-3.5-turbo`, `text-embedding-3-large` models
  - All calls traced via LangFuse if enabled

- [ ] **Swappable at runtime**: dependency injection container allows Anthropic, Gemini, local LLM without code changes

- [ ] **ICardProvider interface** defines contract:
  - `lookup_merchant(provider_id, external_id)` → Dict (merchant details from provider)
  - `list_merchants(provider_id, filters)` → List[Dict]
  - `validate_merchant_data(external_data)` → ValidationResult

- [ ] **Pomelo implementation** (default):
  - Maps Pomelo API fields to Merchant schema

- [ ] **Swappable at runtime**: allows Visa, Mastercard, test providers without code changes

### Transaction Management
- [ ] **contextvars-based ambient transaction context**:
  - `@transactional` decorator on service methods manages SQLAlchemy AsyncSession
  - Session stored in `ContextVar("db_session")` automatically
  - Repositories query current session via `get_db_session()` helper

- [ ] **Nested transaction support**:
  - Inner `@transactional` calls use savepoint
  - Rollback propagates to outer transaction on error

- [ ] **Session scoping**:
  - FastAPI dependency injection provides request-scoped session
  - Multiple service calls within same request share session
  - Session commits after route handler returns (unless error)

- [ ] **Ambient transaction propagation**:
  - Background tasks inherit parent session context if spawned within transaction
  - Non-blocking pipeline steps can read uncommitted data within parent transaction

### Pipeline Engine Framework
- [ ] **BaseEngineService** class:
  - Accepts list of `BaseEngineStep` subclasses
  - Topological sort by `@step(order=...)` decorator
  - Executes blocking steps sequentially in transaction
  - Fires non-blocking steps after transaction commit

- [ ] **@step decorator** syntax:
  ```python
  @step(
      registry="AUTO_CREATION",
      order=1,
      execution_type="blocking",  # or "non_blocking"
      timeout_seconds=30,
      description="Check if merchant exists"
  )
  class CheckExistenceStep(BaseEngineStep):
      async def execute(self, context: PipelineContext) -> PipelineContext:
          # logic here
          return context
      
      def should_run(self, context: PipelineContext) -> bool:
          # skip logic
          return True
  ```

- [ ] **Step discovery**:
  - Auto-registration on import (via NestJS reflection equivalent + Python dataclasses)
  - Registry lookup by name, all steps in registry returned as ordered list

- [ ] **PipelineContext** contains:
  - `input_data: Dict` (initial payload)
  - `state: Dict[str, Any]` (mutable step-to-step data)
  - `trace_id: str` (for LangFuse)
  - `errors: List[Exception]` (accumulated non-fatal errors)

- [ ] **Timeout handling**:
  - Each step wrapped in `asyncio.timeout(step.timeout_seconds)`
  - Timeout raises `StepTimeoutException`, caught and logged by engine
  - Non-fatal errors do NOT stop pipeline

- [ ] **shouldRun() logic**:
  - Each step implements `should_run(context)` check
  - Skipped steps do not execute but remain in trace

- [ ] **Engine execution returns**:
  - `ExecutionResult(status, context, errors, failed_steps, duration_ms)`
  - Status = "success" | "partial" | "failed"

### LLM Provider Integration
- [ ] **LangChain integration**:
  - Uses LangChain agents/chains for multi-step research and analysis
  - LLM research step uses `Tavily` tool for web search

- [ ] **LangFuse tracing**:
  - Every LLM call creates trace in LangFuse
  - Trace includes: prompt, model, tokens_used, temperature
  - Pipeline-level trace aggregates all step traces
  - Fire-and-forget (no blocking on trace delivery in v1)

- [ ] **Embeddings**:
  - All merchant names, MCCs, and metadata embedded via LLM provider
  - Embeddings stored in `Embedding` entity (768-dim for OpenAI)
  - Merchant → Embedding foreign key (one-to-many for versioning)

### Embedding Similarity Search
- [ ] **pgvector integration**:
  - PostgreSQL extension `pgvector` required
  - `Embedding` model maps to vector type (768 dimensions for OpenAI)
  - Cosine similarity queries via `<=>` operator

- [ ] **Similarity search endpoints**:
  - `POST /v1/merchants/search/similarity` — accepts query text or embedding vector
  - Returns merchants ordered by cosine distance, configurable limit (default 10)
  - `POST /v1/mccs/search/similarity` — same for MCC records

- [ ] **Search performance**:
  - Indexes automatically created on Embedding vectors
  - HNSW or IVFFlat index strategy configurable per deployment
  - Sub-millisecond latency for 10-NN queries on 100k merchants (target)

### Auto-Creation Pipeline
- [ ] **Full step sequence** (blocking unless noted):
  1. **CheckExistence**: Query merchant by name (case-insensitive). If exists, skip remaining steps.
  2. **GooglePlace** (blocking or non-blocking): Lookup external merchant metadata via Google Places API. Fills address, phone, category hints.
  3. **LlmResearch** (blocking): Use LangChain agent to research merchant via Tavily. Extract company description, verified website, category candidates.
  4. **Embeddings** (blocking): Generate embeddings for merchant name, description, category candidates via LLM provider.
  5. **MccFallback** (blocking): If no MCC assigned, run similarity search on Mcc embeddings; assign highest-scoring MCC.
  6. **Register** (blocking): Insert Merchant record with assigned MCC, embedding, and metadata flags (human_created=false).
  7. **HumanReview** (non-blocking): Fire webhook/event to human review queue. Wait for approval.
  8. **FinalRegister** (non-blocking): Once approved, mark merchant as reviewed in metadata.

- [ ] **Error handling**:
  - Step timeout (e.g., Google Places API slow) does NOT fail pipeline
  - MCC assignment is optional fallback; register succeeds without MCC
  - Failed steps logged with retry counter in `FailedMerchantCreation`

- [ ] **Idempotency**:
  - CheckExistence step prevents duplicate registration
  - Retrying same pipeline (same input data) returns cached result if exists

### Validation Pipeline
- [ ] **Pre-creation validation** (executes before auto-creation):
  1. **ProviderLookup**: Verify external merchant exists in provider (Pomelo)
  2. **ExistenceCheck**: Query local DB for duplicates by name, provider+id, or embedding similarity
  3. **DataValidation**: Ensure required fields (name, provider, external_id) present and valid
  4. **CategoryValidation**: Validate provided MCC against known categories

- [ ] **Validation result**:
  - Returns list of errors/warnings
  - Pipeline proceeds if warnings only; blocks on errors
  - Errors are returned to caller without attempting creation

### Outbox Event Delivery
- [ ] **Outbox entity**:
  - `id: UUID`
  - `aggregate_id: UUID` (Merchant or Mcc ID)
  - `aggregate_type: str` (e.g., "merchant")
  - `event_type: str` (e.g., "MerchantCreated", "MerchantUpdated")
  - `payload: JSON` (event data)
  - `status: str` ("pending" | "delivered" | "failed")
  - `attempts: int` (retry counter)
  - `max_attempts: int = 5`
  - `created_at: datetime`
  - `delivered_at: Optional[datetime]`
  - `error_message: Optional[str]`
  - `idempotency_key: str` (unique per event)

- [ ] **Outbox writer**:
  - Called within `@transactional` method
  - Event inserted in same transaction as business operation
  - Example: `outbox_service.emit(Merchant, merchant_id, "created", merchant.to_dict())`

- [ ] **Outbox processor** (background worker):
  - Polls every 5 seconds (configurable)
  - Fetches up to 100 pending events
  - Calls downstream service (e.g., Voucher microservice)
  - On success: marks status="delivered", sets delivered_at
  - On failure: increments attempts, exponential backoff (2^attempts seconds until next retry)
  - Alerts if event stuck >30 minutes

- [ ] **Idempotency**:
  - Each event has idempotency_key (UUID or hash of aggregate+event_type+timestamp)
  - Downstream service can replay failed events; must use idempotency_key to deduplicate

### MCC Classification
- [ ] **MCC entity**:
  - `id: UUID`
  - `code: str` (4-digit code, unique)
  - `description: str`
  - `category_id: FK → Category`
  - `embedding: Vector` (768-dim)
  - `parent_mcc_id: Optional[FK]` (for hierarchical codes)
  - `created_at, updated_at: datetime`

- [ ] **Category entity**:
  - `id: UUID`
  - `name: str` (unique, e.g., "Grocery", "Hotels", "Gas Stations")
  - `description: Optional[str]`

- [ ] **MCC CRUD**:
  - Create MCC with auto-embedding via LLM provider
  - List MCCs with pagination, category filters
  - Update MCC (description, category, embedding)
  - Similarity search: `POST /v1/mccs/search/similarity` returns MCCs by vector distance

- [ ] **Default MCCs**:
  - Seeded from standard ISO 18245 MCC list (up to 1000 codes)
  - Organized into 21 major categories

---

## Acceptance Scenarios

### 1. FastAPI Merchant API

#### Happy Path: Create, Read, Update, Delete Merchant

```gherkin
Scenario: Create a merchant with minimal data
  Given I have a valid HMAC signature for the request
  When I POST /v1/merchants with:
    {
      "name": "Whole Foods Market",
      "provider_id": "POMELO",
      "external_id": "ext_12345",
      "metadata": { "human_created": false }
    }
  Then the response status is 201
  And the response body contains:
    - id: UUID (generated)
    - name: "WHOLE FOODS MARKET" (uppercased)
    - created_at: ISO8601 timestamp
    - embedding: null (will be generated async)
    - metadata.human_created: false

Scenario: Read a created merchant
  Given I have created a merchant with id "abc-123"
  When I GET /v1/merchants/abc-123 with valid HMAC
  Then the response status is 200
  And the response body contains all merchant fields

Scenario: Update merchant name and metadata
  Given I have a merchant with id "abc-123" and name "WHOLE FOODS"
  When I PUT /v1/merchants/abc-123 with:
    {
      "name": "Whole Foods - Midtown",
      "metadata": { "human_modified": true }
    }
  Then the response status is 200
  And the merchant.name is "WHOLE FOODS - MIDTOWN"
  And the merchant.metadata.human_modified is true
  And the merchant.updated_at is NOW

Scenario: Soft-delete a merchant
  Given I have a merchant with id "abc-123"
  When I DELETE /v1/merchants/abc-123 with valid HMAC
  Then the response status is 204
  When I GET /v1/merchants/abc-123 again
  Then the response status is 404 (or 410 Gone)
  And the merchant.deleted_at is NOT NULL (in database)

Scenario: List merchants with pagination
  Given there are 25 merchants in the database
  When I GET /v1/merchants?limit=10&offset=0 with valid HMAC
  Then the response status is 200
  And the response body contains:
    - data: List[Merchant] (10 items)
    - pagination: { total: 25, limit: 10, offset: 0 }

Scenario: HMAC authentication fails
  Given I have a request with invalid HMAC signature
  When I POST /v1/merchants with valid data
  Then the response status is 401 Unauthorized
  And the response contains "Invalid HMAC signature"
```

#### Edge Cases: Bulk Operations

```gherkin
Scenario: Bulk create merchants
  Given I have a valid HMAC signature
  When I POST /v1/merchants/bulk/create with:
    {
      "merchants": [
        { "name": "Whole Foods", "external_id": "ext_1" },
        { "name": "Trader Joe's", "external_id": "ext_2" }
      ]
    }
  Then the response status is 207 Multi-Status
  And the response body contains:
    - created: [{ id, name }, ...] (both succeeded)
    - errors: [] (none)

Scenario: Bulk create with partial failure
  Given I have 2 merchants where one has a duplicate external_id
  When I POST /v1/merchants/bulk/create
  Then the response status is 207
  And the response body contains:
    - created: [{ id, name }] (1 succeeded)
    - errors: [{ index: 1, message: "duplicate external_id" }]

Scenario: Bulk update merchants
  Given I have 3 merchants in the database
  When I POST /v1/merchants/bulk/update with:
    {
      "updates": [
        { "id": "abc-123", "metadata": { "human_modified": true } },
        { "id": "xyz-789", "name": "Updated Name" }
      ]
    }
  Then the response status is 200
  And all updates are applied within same transaction
```

#### Failure Modes: Validation and Constraints

```gherkin
Scenario: Create merchant with invalid data
  Given I POST /v1/merchants with:
    { "name": null, "external_id": "ext_1" }
  Then the response status is 422 Unprocessable Entity
  And the response body contains validation error for "name"

Scenario: Create merchant with duplicate name and provider
  Given a merchant named "WHOLE FOODS" with provider "POMELO" already exists
  When I POST /v1/merchants with:
    { "name": "Whole Foods", "provider_id": "POMELO", "external_id": "ext_new" }
  Then the response status is 409 Conflict
  And the response contains "merchant already exists"
```

---

### 2. MCC Classification API

#### Happy Path: MCC CRUD

```gherkin
Scenario: Create an MCC with description
  Given I have a valid HMAC signature
  When I POST /v1/mccs with:
    {
      "code": "5411",
      "description": "Grocery stores and supermarkets",
      "category_id": "grocery-cat-uuid"
    }
  Then the response status is 201
  And the response body contains:
    - id: UUID
    - code: "5411"
    - embedding: Vector[768] (generated from description)

Scenario: List all MCCs with category filter
  Given there are 50 MCCs in database across 3 categories
  When I GET /v1/mccs?category_id=grocery-cat-uuid&limit=20 with valid HMAC
  Then the response status is 200
  And the response contains 20 grocery MCCs
  And pagination info

Scenario: Update MCC category
  Given an MCC with id "mcc-1" in "Grocery" category
  When I PUT /v1/mccs/mcc-1 with:
    { "category_id": "restaurants-cat-uuid" }
  Then the response status is 200
  And the MCC.category_id is updated
  And the MCC.embedding is regenerated if description changed
```

---

### 3. Embedding Similarity Search

#### Happy Path: Vector Similarity Queries

```gherkin
Scenario: Search merchants by text query (auto-embed)
  Given 100 merchants exist with embeddings
  When I POST /v1/merchants/search/similarity with:
    {
      "query": "coffee shops",
      "limit": 5,
      "similarity_threshold": 0.7
    }
  Then the response status is 200
  And the response contains:
    - results: [
        { id, name, similarity_score: 0.95 },
        { id, name, similarity_score: 0.88 },
        ...
      ] (5 items, sorted by similarity DESC)

Scenario: Search MCCs by embedding vector
  Given I have a pre-computed embedding vector [0.1, 0.2, ...]
  When I POST /v1/mccs/search/similarity with:
    {
      "embedding": [0.1, 0.2, ...],
      "limit": 10
    }
  Then the response status is 200
  And the response contains 10 MCCs ordered by cosine distance

Scenario: Empty search result
  Given I search for an obscure query with no close matches
  When I POST /v1/merchants/search/similarity with query + threshold 0.95
  Then the response status is 200
  And results: [] (empty list, not error)
```

---

### 4. Pipeline Engine Framework

#### Happy Path: Multi-Step Pipeline Execution

```gherkin
Scenario: Execute auto-creation pipeline successfully
  Given the AutoCreationEngine has 8 steps registered
  When I call engine.execute() with:
    {
      "merchant_name": "Whole Foods Market",
      "provider_id": "POMELO",
      "external_id": "ext_12345"
    }
  Then the pipeline executes:
    1. CheckExistence (blocking) — searches DB, finds no match
    2. GooglePlace (blocking) — fetches address, phone
    3. LlmResearch (blocking) — calls Tavily + LLM, gets description
    4. Embeddings (blocking) — generates vector
    5. MccFallback (blocking) — assigns highest-scoring MCC
    6. Register (blocking) — inserts Merchant record
    7. HumanReview (non-blocking) — fires event (returns immediately)
    8. FinalRegister (non-blocking) — marks reviewed (in background)
  And the response contains:
    {
      "status": "success",
      "merchant_id": UUID,
      "errors": [],
      "duration_ms": 2500
    }

Scenario: Pipeline with step timeout
  Given GooglePlace step has timeout_seconds=5
  When GooglePlace API takes 10 seconds to respond
  Then the step timeout triggers after 5 seconds
  And the exception is caught and logged
  And the pipeline continues to LlmResearch
  And the final status is "partial" (not "failed")
  And the context.errors contains the timeout exception

Scenario: shouldRun() skips step conditionally
  Given a pipeline step with shouldRun() checking for MCC assignment
  When the context already has an MCC assigned
  Then the MccFallback step should_run() returns False
  And the step is skipped (not executed)
  And the trace logs "step skipped"
```

#### Edge Cases: Error Handling

```gherkin
Scenario: Non-blocking step failure does not roll back transaction
  Given the Register (blocking) step has committed a Merchant record
  When HumanReview (non-blocking) step throws exception
  Then the Merchant record remains in database
  And the exception is logged asynchronously
  And the pipeline engine returns status="partial"

Scenario: Multiple non-blocking steps execute in parallel
  Given HumanReview and FinalRegister are both non-blocking
  When the blocking steps complete
  Then both non-blocking steps are submitted to background task queue
  And they execute concurrently (no ordering guarantee)
  And the pipeline returns immediately to caller
```

---

### 5. LLM Provider Abstraction

#### Happy Path: Provider Swapping

```gherkin
Scenario: Default OpenAI provider is used
  Given ILlmProvider is configured with OpenAI
  When I call llm_provider.generate(prompt="Describe this merchant")
  Then the request is sent to OpenAI API
  And the response is a string (generated text)
  And LangFuse logs the call with tokens_used

Scenario: Swap to Anthropic provider at runtime
  Given I have an Anthropic implementation of ILlmProvider
  When I update the DI container to use AnthropicLlmProvider
  And I call llm_provider.generate()
  Then the request is sent to Anthropic API
  And the response is identical format (no code changes to pipeline)
  And LangFuse logs with "anthropic" model tag

Scenario: Embed text via LLM provider
  Given I call llm_provider.embed(text="Whole Foods", model="text-embedding-3-large")
  Then the response is a List[float] with 768 elements
  And the vector is normalized (magnitude ~ 1.0)
  And LangFuse logs the embedding call
```

#### Edge Cases: Provider Failures

```gherkin
Scenario: OpenAI API is down
  Given the OpenAI provider receives a 503 Service Unavailable
  When I call llm_provider.generate()
  Then the exception is raised (does NOT retry)
  And the pipeline step catches it
  And the step's timeout or error handler logs the failure

Scenario: Research step with Tavily search
  Given I call llm_provider.research(query="best grocery stores in NYC")
  Then the LangChain agent uses Tavily tool
  And the response is a List[Dict] with search results
  And each result contains: title, url, snippet, relevance_score
```

---

### 6. Card/Transaction Provider Abstraction

#### Happy Path: Provider Lookup and Swapping

```gherkin
Scenario: Default Pomelo provider lookup
  Given ICardProvider is configured with Pomelo
  When I call card_provider.lookup_merchant(provider_id="POMELO", external_id="ext_12345")
  Then the request is sent to Pomelo API
  And the response contains merchant details from Pomelo
  And the data is mapped to Merchant schema

Scenario: Swap to test provider for development
  Given I have a TestCardProvider (in-memory mock)
  When I update DI container to use TestCardProvider
  And I call card_provider.lookup_merchant()
  Then the response is from in-memory mock data
  And pipeline continues without hitting real Pomelo API

Scenario: Validate external merchant data
  Given I call card_provider.validate_merchant_data(external_data)
  When the external_data has required fields (name, provider_id, external_id)
  Then the response is ValidationResult(is_valid=True, errors=[])
```

#### Edge Cases: Validation Failures

```gherkin
Scenario: External merchant data is invalid
  Given external_data is missing required "name" field
  When I call card_provider.validate_merchant_data(external_data)
  Then the response is ValidationResult(is_valid=False, errors=["name required"])
  And the pipeline validation step blocks with errors
```

---

### 7. Transaction Management

#### Happy Path: Ambient Transaction Context

```gherkin
Scenario: Service method uses @transactional decorator
  Given I have a service method decorated with @transactional
  When the method is called:
    async def create_merchant(data):
      @transactional
      async def _do_create():
        merchant = Merchant(**data)
        db.session.add(merchant)
        # session is auto-committed after method returns
  Then the Merchant is inserted into database
  And the transaction is committed automatically
  And the session is cleaned up

Scenario: Session is shared across nested service calls
  Given service_a.create_merchant() calls service_b.assign_mcc()
  When both are decorated with @transactional
  Then service_b reuses the same SQLAlchemy session from service_a
  And both operations commit together (same transaction)

Scenario: Rollback on error
  Given a service method decorated with @transactional
  When an exception is raised inside the method
  Then the transaction is rolled back automatically
  And no data is persisted
  And the exception is re-raised to caller
```

#### Edge Cases: Nested Transactions and Savepoints

```gherkin
Scenario: Nested @transactional with savepoint
  Given an outer @transactional method calls inner @transactional
  When inner method raises exception
  Then a savepoint is created for inner transaction
  And the savepoint is rolled back (only inner changes undone)
  And the outer transaction continues
  And outer can commit its changes

Scenario: Background task inherits transaction context
  Given a non-blocking pipeline step spawns background task
  When the task queries the database
  Then it can read uncommitted data from parent transaction (if explicitly allowed)
  Or it waits for parent to commit (default behavior)
```

---

### 8. Auto-Creation Pipeline

#### Happy Path: Full Pipeline Execution

```gherkin
Scenario: Auto-creation from external merchant data
  Given I have Pomelo merchant data:
    {
      "provider_id": "POMELO",
      "external_id": "ext_12345",
      "name": "Whole Foods Market",
      "address": "123 Main St"
    }
  When I call auto_creation_engine.execute(external_merchant_data)
  Then the pipeline executes:
    1. CheckExistence searches DB by name (case-insensitive)
    2. GooglePlace fetches metadata (no error if API fails)
    3. LlmResearch uses Tavily to research company
    4. Embeddings generates vector for name + description
    5. MccFallback searches Mcc embeddings, assigns highest-scoring MCC
    6. Register inserts Merchant record (human_created=false)
    7. HumanReview emits event to review queue (non-blocking)
    8. FinalRegister polls for approval (non-blocking)
  And the response contains:
    {
      "status": "success",
      "merchant": { id, name, mcc_id, ... },
      "trace_id": UUID (for LangFuse)
    }

Scenario: MCC fallback when no explicit assignment
  Given the AutoCreationEngine has no explicit MCC in input
  When MccFallback step runs
  Then it generates embedding for merchant description
  And searches Mcc embeddings with cosine similarity
  And assigns merchant to highest-scoring MCC (>= 0.6 threshold)
  And stores assignment with metadata.mcc_type="auto_matched"

Scenario: Register step inserts ExternalMerchant mapping
  Given the pipeline has resolved a Merchant
  When Register step executes
  Then it also inserts ExternalMerchant record with:
    - provider="POMELO"
    - external_id="ext_12345"
    - merchant_id=UUID (FK to Merchant)
    - metadata={ sync_status="active" }
```

#### Edge Cases: Idempotency and Retry

```gherkin
Scenario: Retry same auto-creation request
  Given I called auto_creation_engine.execute() and got success
  When I call the exact same request again (same input data)
  Then CheckExistence finds the merchant
  And the pipeline returns immediately with cached merchant_id
  And no duplicate is created

Scenario: Failed creation tracked in FailedMerchantCreation
  Given the Register step throws database error
  When the pipeline fails
  Then an entry is inserted into FailedMerchantCreation:
    - external_merchant_id: UUID
    - error_message: string
    - retry_count: 0
    - last_attempted_at: NOW
  And the pipeline can be retried by background job

Scenario: Failed creation with retry limit
  Given a merchant has failed 5 times (FailedMerchantCreation.retry_count=5)
  When a background job attempts retry
  Then it increments retry_count to 6
  And checks if retry_count > max_retries (5)
  And marks the failed creation as "abandoned"
  And alerts operations team
```

---

### 9. Outbox Event Delivery

#### Happy Path: Event Publishing and Processing

```gherkin
Scenario: Merchant creation emits event via outbox
  Given I create a Merchant record with auto-creation pipeline
  When the Register step completes
  Then it calls outbox_service.emit():
    {
      "aggregate_id": merchant_id,
      "aggregate_type": "merchant",
      "event_type": "MerchantCreated",
      "payload": { name, mcc_id, embedding, ... }
    }
  And the Outbox record is inserted in SAME transaction as Merchant
  And the Outbox.status="pending"
  And the Outbox.idempotency_key is generated

Scenario: Outbox worker processes pending events
  Given 10 pending events in Outbox table
  When the OutboxProcessor polls:
    - Fetches next 100 pending events
    - For each event, calls downstream service (e.g., Voucher microservice)
  Then on success:
    - Outbox.status="delivered"
    - Outbox.delivered_at=NOW
  And on failure:
    - Outbox.attempts is incremented
    - Outbox.error_message is updated
    - Event is retried after exponential backoff (2^attempts seconds)

Scenario: Idempotency key prevents duplicate processing
  Given an Outbox event with idempotency_key="ik_xyz"
  When the Voucher microservice processes it and ACKs
  And the outbox worker receives same event (e.g., due to retry logic)
  Then Voucher microservice rejects with "idempotency_key already processed"
  And the outbox worker marks event as delivered anyway
  And no duplicate is created in Voucher

Scenario: Event stuck in outbox >30 minutes
  Given an event has been retried 10 times over 2 hours
  When the monitoring system detects attempts > max_attempts
  Then an alert is sent (email/Slack to ops)
  And the event is marked as "failed" (no more retries)
  And a manual review ticket is created
```

#### Edge Cases: Failure Handling

```gherkin
Scenario: Downstream service is down
  Given the Voucher microservice is unavailable
  When the outbox worker tries to deliver event
  Then the request times out (5 second timeout)
  And the exception is caught
  And attempts is incremented
  And event is retried after 2 seconds (2^1)

Scenario: Downstream service returns 400 Bad Request
  Given the outbox event payload is malformed
  When Voucher microservice returns 400
  Then the event is marked as "failed" immediately (not retried)
  And the error_message is logged
  And manual review is required

Scenario: Multiple events for same merchant
  Given a Merchant is created, then updated 3 times
  When outbox worker processes all 4 events (1 create + 3 updates)
  Then each event is processed independently
  And Voucher microservice receives all 4 events (in order, if ordering matters)
  And order is guaranteed by outbox table ordering
```

---

## Out of Scope (v1.0)

The following capabilities are explicitly deferred:

- **Multi-tenancy**: v1 assumes single-tenant; v2 will add tenant isolation via schema/row-level security
- **Event Sourcing**: Outbox pattern only; full event store deferred
- **GraphQL API**: REST only; GraphQL port deferred to v2
- **Real-time WebSocket**: HTTP polling/webhook callbacks only
- **Langfuse custom dashboard**: Traces fire-and-forget; custom Langfuse dashboard deferred
- **OAuth/OIDC**: HMAC + JWT only; OAuth deferred
- **Blue-green deployment**: Standard containerization; advanced deployment strategies deferred
- **DynamoDB integration**: PostgreSQL only; DynamoDB deferred to v2
- **SNS event publishing**: Webhook callbacks only; SNS integration deferred to v2
- **Distributed tracing** (OpenTelemetry): Fire-and-forget Langfuse traces only; full distributed tracing deferred
- **GraphQL subscriptions**: N/A (REST only in v1)
- **Batch processing with SQS**: Outbox worker only; SQS integration deferred

---

## Success Metrics

### Functional Completeness
- [ ] All 19 API endpoints operational and tested (14 merchants + 5 MCCs + health)
- [ ] All 9 entities fully mapped to SQLAlchemy with correct relationships
- [ ] Pipeline engine supports ≥8 concurrent steps with timeout and shouldRun() logic
- [ ] LLM provider abstraction allows OpenAI ↔ Anthropic swap without code changes
- [ ] Card provider abstraction allows Pomelo ↔ test provider swap without code changes
- [ ] Auto-creation and Validation pipelines execute end-to-end with realistic data
- [ ] Outbox worker retries failed events and survives 1-hour database downtime

### Performance
- [ ] Vector similarity search sub-millisecond latency (p99 < 100ms on 100k merchants)
- [ ] Auto-creation pipeline completes in <10 seconds (blocking steps only)
- [ ] Outbox worker processes 100+ events per poll without blocking main app

### Test Coverage
- [ ] Services layer: ≥75% coverage
- [ ] Pipeline engine: ≥80% coverage
- [ ] Database/ORM: ≥70% coverage
- [ ] HTTP layer (routers): ≥50% coverage (acceptable for fast-moving API)

### Operability
- [ ] Docker Compose brings up all services with `docker-compose up`
- [ ] App connects to database on first request
- [ ] Health check endpoint returns status of database + outbox worker
- [ ] Logs are structured (JSON) and queryable

### Documentation
- [ ] OpenAPI schema complete and valid (Swagger UI functional)
- [ ] README.md with setup, architecture, key commands
- [ ] Provider interface contracts documented with examples
- [ ] Pipeline engine README with @step decorator usage

---

## Testing Strategy

### Unit Tests
- **Models**: Relationships, constraints, soft deletes, UPPERCASE enforcement on Merchant.name
- **Services**: Business logic isolation, mocking external providers, transaction rollback
- **Pipeline steps**: shouldRun() logic, timeout handling, context mutations
- **Providers**: Mocking LLM and card provider interfaces

### Integration Tests
- **Full pipeline execution**: Auto-creation end-to-end with test data
- **Database transactions**: Nested savepoints, rollback, commit
- **Outbox delivery**: Event publishing + processing + idempotency
- **Vector similarity**: Search accuracy on seed data

### Acceptance Tests
- **API endpoints**: All 19 endpoints with valid/invalid payloads, HMAC auth
- **Provider swapping**: Alternate LLM/card provider and verify behavior
- **Docker Compose**: Services startup and connectivity

---

## Risk Mitigations

| Risk | Mitigation |
|------|-----------|
| **Async context propagation bugs** | Extensive pytest fixtures isolating contextvars per test; custom context manager for cleanup |
| **pgvector performance on large datasets** | Index optimization, query planning in CI; benchmark 100k+ merchants early |
| **LLM provider swapping complexity** | Interface-first design; mock all providers in tests; document all assumptions in ILlmProvider |
| **Event delivery guarantees** | Idempotency key mandatory; test Outbox worker under failure scenarios; alerting on stuck events |
| **Docker Compose tooling drift** | Pin all service image versions; validate in CI |
| **Pomelo field mapping gaps** | Document all ExternalMerchant field mappings before auto-creation phase; validate against live Pomelo schema |
| **Schema migration reversibility** | Test rollback on every Alembic migration; require downgrade scripts |

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2026-05-13 | Initial specification for v1.0 release |

