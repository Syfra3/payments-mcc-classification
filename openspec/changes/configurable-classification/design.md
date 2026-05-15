# Design: Configurable Classification System

## Technical Approach

Transform the tightly-coupled MccClassificationStep (which uses OpenAI exclusively) into a pluggable classification pipeline via the IClassifier interface and factory pattern. Tenant isolation is achieved through row-level filtering on merchants, categories, and MCCs using a tenant_id column. Configuration drives classifier selection at runtime (environment variable), enabling zero-code deployments of different strategies (LLM, rule-based, lookup-table).

The core insight: move classification logic OUT of the pipeline step and INTO strategy-specific classifier services. The step becomes a thin orchestrator that selects the right classifier via factory, passes tenant context, and handles results.

## Architecture Decisions

| Decision | Choice | Alternatives | Rationale |
|----------|--------|--------------|-----------|
| **Classifier abstraction** | IClassifier ABC + factory pattern | Hardcoded conditional logic | Enables runtime strategy swap without code changes; testable in isolation |
| **Tenant context flow** | PipelineContext carries tenant_id as dict key | HTTP header + middleware | Aligns with existing pipeline pattern; consistent with how `name`, `description` flow through steps |
| **Rule file loading** | Lazy load + cache at step init; re-read on config change | Load at app startup | Supports multi-tenant rule sets per deployment; no app restart needed for rule updates |
| **Tenant identifier** | String (40 chars max, lowercase) | UUID | Human-readable, database-friendly, matches SaaS conventions; indexes efficiently |
| **Repository scoping** | Add tenant_id WHERE clause to existing queries | Separate tenant-scoped repositories | Minimal disruption; single responsibility (query filtering, not class redesign) |
| **Migration ordering** | Add columns → backfill → add constraints → add indexes | Separate migrations per concern | Atomic operation per logical unit; easier rollback; clear audit trail |
| **Classifier factory location** | `app/services/classifiers/factory.py` | Global singleton | Instance-based factory supports testing; dependency injection ready |
| **LLMClassifier wrapping** | Minimal wrapper around existing LlmProvider | Rewrite classification logic | Preserves battle-tested OpenAI integration; reduces regression risk |

## Data Flow

```
HTTP Request
    ↓
[Pipeline Engine]
    ├─ context.tenant_id = "default" (from header or default)
    ├─ context.name, description = request payload
    ↓
[MccClassificationStep]
    ├─ factory.get_classifier(context.tenant_id) → IClassifier instance
    ├─ selected = LLMClassifier | RuleBasedClassifier | LookupTableClassifier
    ↓
[Chosen Classifier]
    ├─ classify(merchant_name, tenant_id) async
    ├─ Access MccRepository/CategoryRepository (tenant-scoped queries)
    ├─ Return ClassificationResult { mcc_codes, confidence, source }
    ↓
[MccClassificationStep returns result]
    ├─ context.set("mcc_codes", result.mcc_codes)
    ↓
[Downstream steps in pipeline]
    └─ Use context.mcc_codes as before
```

**Tenant context propagation:**
- API endpoint sets `context.tenant_id` from request header `X-Tenant-ID` or uses config default
- Pipeline passes context to all steps
- Repositories use tenant_id in WHERE clause for all queries
- Classifiers never query directly; use repositories (which enforce tenant scoping)

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `app/services/classifiers/__init__.py` | Create | Package marker |
| `app/services/classifiers/base.py` | Create | IClassifier ABC + ClassificationResult dataclass |
| `app/services/classifiers/llm_classifier.py` | Create | LLMClassifier wrapping existing OpenAI logic |
| `app/services/classifiers/rule_based_classifier.py` | Create | RuleBasedClassifier with YAML pattern loading |
| `app/services/classifiers/lookup_classifier.py` | Create | LookupTableClassifier for direct MCC lookups |
| `app/services/classifiers/factory.py` | Create | ClassifierFactory singleton for runtime strategy selection |
| `app/pipeline/auto_creation/mcc_classification.py` | Modify | Rename to TopicClassificationStep; inject classifier via factory |
| `app/models/mcc.py` | Modify | Add tenant_id to Category, Mcc, MerchantMcc; update unique constraints |
| `app/models/merchant.py` | Modify | Add tenant_id column |
| `app/core/config.py` | Modify | Add CLASSIFIER_TYPE, CLASSIFIER_RULES_PATH, DEFAULT_TENANT, DEMO_TOPICS |
| `app/repositories/mcc_repository.py` | Modify | Add tenant_id WHERE filtering to all queries |
| `app/repositories/merchant_repository.py` | Modify | Add tenant_id WHERE filtering to all queries |
| `app/repositories/embedding_repository.py` | Modify | Add tenant_id WHERE filtering if applicable |
| `alembic/versions/003_add_tenant_isolation.py` | Create | Migration: add tenant_id columns, backfill, constraints, indexes |
| `config/demo_topics.yaml` | Create | Pre-loaded demo categories for FARMACIA, SUPERMERCADO, RESTAURANTE, SERVICIOS, OTROS |
| `tests/unit/test_classifier_factory.py` | Create | Unit tests for factory and classifier selection |
| `tests/unit/test_rule_based_classifier.py` | Create | Unit tests for rule pattern matching |
| `tests/integration/test_tenant_isolation.py` | Create | Integration tests verifying tenant scoping |

## Interfaces / Contracts

### ClassificationResult

```python
from dataclasses import dataclass

@dataclass
class ClassificationResult:
    """Result of a classification operation."""
    mcc_codes: list[str]
    confidence: float  # 0.0-1.0
    source: str  # "llm", "rule", "lookup"
    error: Optional[str] = None
    metadata: dict = None  # Additional context (matched rules, search results, etc)
```

### IClassifier Interface

```python
from abc import ABC, abstractmethod

class IClassifier(ABC):
    """Abstract base for classification strategies."""

    @abstractmethod
    async def classify(
        self, 
        merchant_name: str, 
        tenant_id: str,
        description: Optional[str] = None,
    ) -> ClassificationResult:
        """
        Classify a merchant name into MCCs.
        
        Args:
            merchant_name: Name to classify (uppercase expected)
            tenant_id: Tenant context (filters rules, MCCs, categories)
            description: Optional merchant description for context
            
        Returns:
            ClassificationResult with mcc_codes, confidence, source
            
        Raises:
            TenantNotFoundError: If tenant_id does not exist
            ClassifierError: If classification fails
        """
        pass
```

### ClassifierFactory

```python
class ClassifierFactory:
    """Factory for creating classifier instances based on config."""
    
    def __init__(self, config: Settings):
        """Initialize with config (CLASSIFIER_TYPE, CLASSIFIER_RULES_PATH, etc)."""
        pass
    
    async def get_classifier(self, tenant_id: str) -> IClassifier:
        """
        Get appropriate classifier instance for tenant.
        
        Routes to:
        - LLMClassifier if CLASSIFIER_TYPE == "llm"
        - RuleBasedClassifier if CLASSIFIER_TYPE == "rules"
        - LookupTableClassifier if CLASSIFIER_TYPE == "lookup"
        """
        pass
```

### Config Extensions

```python
class Settings(BaseSettings):
    # ... existing fields ...
    
    # Classification config
    classifier_type: str = "llm"  # "llm" | "rules" | "lookup"
    classifier_rules_path: str = "/config/rules"
    default_tenant: str = "default"
    demo_topics: bool = True  # Auto-load demo categories on startup
```

## Repository Scoping Pattern

Example: MccRepository tenant-scoped queries

```python
class MccRepository:
    async def get_by_code(self, code: str, tenant_id: str) -> Optional[Mcc]:
        """Get MCC by code, scoped to tenant."""
        session = self._get_session()
        stmt = select(Mcc).where(
            and_(
                Mcc.code == code,
                Mcc.tenant_id == tenant_id,
                Mcc.deleted_at.is_(None),
            )
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()
    
    async def list_all(self, tenant_id: str, skip: int = 0, limit: int = 100) -> List[Mcc]:
        """List all MCCs for tenant."""
        session = self._get_session()
        stmt = (
            select(Mcc)
            .where(
                and_(
                    Mcc.tenant_id == tenant_id,
                    Mcc.deleted_at.is_(None),
                )
            )
            .offset(skip)
            .limit(limit)
        )
        result = await session.execute(stmt)
        return result.scalars().all()
```

Apply the same pattern (add `tenant_id` parameter, add WHERE clause) to:
- MccRepository: get_by_code, get_by_id, list_all, search_by_similarity
- CategoryRepository: get_by_id, get_by_name, list_all
- MerchantRepository: get_by_id, get_by_name, list_all
- EmbeddingRepository: if querying cross-tenant embeddings

## RuleBasedClassifier Implementation

**Rule file format** (`categories/{tenant_id}/rules.yaml`):

```yaml
rules:
  - name: "FARMACIA"
    patterns:
      - "FARM"
      - "DROGUE"
      - "PHARMACY"
    mcc_codes: ["5912"]
    confidence: 0.95
  
  - name: "SUPERMERCADO"
    patterns:
      - "SUPER"
      - "MERCADO"
      - "GROCERY"
    mcc_codes: ["5411", "5412"]
    confidence: 0.90

  - name: "RESTAURANTE"
    patterns:
      - "REST"
      - "CAFE"
      - "PIZZ"
    mcc_codes: ["5812"]
    confidence: 0.85
```

**Loading & Caching:**
- At step init: load `categories/{tenant_id}/rules.yaml`
- Cache in-memory per tenant (LRU cache, 100 tenants max)
- On cache miss: load from filesystem
- Pattern matching: case-insensitive substring match; return first matched rule

## LookupTableClassifier

Direct MCC lookup without inference:

```python
class LookupTableClassifier(IClassifier):
    async def classify(self, merchant_name: str, tenant_id: str, description: Optional[str] = None) -> ClassificationResult:
        # Query for exact match in merchant table
        merchant = await merchant_repo.get_by_name(merchant_name, tenant_id)
        if merchant and merchant.mccs:
            return ClassificationResult(
                mcc_codes=[mcc.code for mcc in merchant.mccs],
                confidence=1.0,
                source="lookup",
            )
        
        # Fallback: no match found
        return ClassificationResult(
            mcc_codes=[],
            confidence=0.0,
            source="lookup",
            error="no_merchant_found",
        )
```

## LLMClassifier

Minimal wrapper preserving existing logic:

```python
class LLMClassifier(IClassifier):
    def __init__(self, llm_provider: ILlmProvider, mcc_repo: MccRepository):
        self._llm = llm_provider
        self._mcc_repo = mcc_repo
    
    async def classify(self, merchant_name: str, tenant_id: str, description: Optional[str] = None) -> ClassificationResult:
        # Reuse existing MccClassificationStep.execute() logic
        # Pass tenant_id to mcc_repo.get_by_code(code, tenant_id)
        # Return ClassificationResult instead of raw dict
```

## Demo Topic Loader

**File:** `config/demo_topics.yaml`

```yaml
default:
  categories:
    - name: FARMACIA
      description: Farmacias y droguerías
    - name: SUPERMERCADO
      description: Supermercados y almacenes
    - name: RESTAURANTE
      description: Restaurantes y bares
    - name: SERVICIOS
      description: Servicios (plomería, electricidad, etc)
    - name: OTROS
      description: Otros
```

**Loader function** in `app/core/lifecycle.py`:

```python
async def load_demo_topics():
    """Load demo topics on app startup if enabled."""
    if not settings.demo_topics:
        return
    
    category_repo = CategoryRepository()
    
    # Load default tenant categories
    for cat_def in load_yaml("config/demo_topics.yaml")["default"]["categories"]:
        existing = await category_repo.get_by_name(cat_def["name"])
        if not existing:
            category = Category(
                name=cat_def["name"],
                description=cat_def["description"],
                tenant_id="default",
            )
            await category_repo.create(category)
```

Call in app startup event:

```python
@app.on_event("startup")
async def startup():
    await load_demo_topics()
    # ... other startup logic
```

## Database Migration Strategy

**File:** `alembic/versions/003_add_tenant_isolation.py`

```python
def upgrade() -> None:
    # Step 1: Add tenant_id columns
    op.add_column("merchant", sa.Column("tenant_id", sa.String(100), nullable=True))
    op.add_column("category", sa.Column("tenant_id", sa.String(100), nullable=True))
    op.add_column("mcc", sa.Column("tenant_id", sa.String(100), nullable=True))
    
    # Step 2: Backfill with default tenant
    op.execute("UPDATE merchant SET tenant_id = 'default' WHERE tenant_id IS NULL")
    op.execute("UPDATE category SET tenant_id = 'default' WHERE tenant_id IS NULL")
    op.execute("UPDATE mcc SET tenant_id = 'default' WHERE tenant_id IS NULL")
    
    # Step 3: Set NOT NULL constraint
    op.alter_column("merchant", "tenant_id", nullable=False)
    op.alter_column("category", "tenant_id", nullable=False)
    op.alter_column("mcc", "tenant_id", nullable=False)
    
    # Step 4: Create indexes
    op.create_index("ix_merchant_tenant_id", "merchant", ["tenant_id"])
    op.create_index("ix_category_tenant_id", "category", ["tenant_id"])
    op.create_index("ix_mcc_tenant_id", "mcc", ["tenant_id"])
    
    # Step 5: Update unique constraints
    op.drop_constraint("uq_category_name", "category", type_="unique")
    op.create_unique_constraint(
        "uq_category_name_tenant_id",
        "category",
        ["name", "tenant_id"],
    )
    
    op.drop_constraint("uq_mcc_code", "mcc", type_="unique")
    op.create_unique_constraint(
        "uq_mcc_code_tenant_id",
        "mcc",
        ["code", "tenant_id"],
    )

def downgrade() -> None:
    # Reverse: drop constraints, columns
    op.drop_constraint("uq_category_name_tenant_id", "category", type_="unique")
    op.create_unique_constraint("uq_category_name", "category", ["name"])
    
    op.drop_constraint("uq_mcc_code_tenant_id", "mcc", type_="unique")
    op.create_unique_constraint("uq_mcc_code", "mcc", ["code"])
    
    op.drop_index("ix_merchant_tenant_id")
    op.drop_index("ix_category_tenant_id")
    op.drop_index("ix_mcc_tenant_id")
    
    op.drop_column("merchant", "tenant_id")
    op.drop_column("category", "tenant_id")
    op.drop_column("mcc", "tenant_id")
```

**Estimated downtime:** < 1 minute (backfill is O(n), no blocking schema changes).

## Error Handling

**Failure scenarios:**

| Scenario | Handler | Fallback |
|----------|---------|----------|
| Classifier unavailable | Log error, return ClassificationResult.error | Return empty mcc_codes |
| Tenant not found | Raise TenantNotFoundError (halts step) | Reject request with 400 |
| Rule file syntax invalid | Log, skip that rule | Continue with other rules |
| LLM API timeout | Retry once; timeout, return error | Fallback to lookup if configured |
| Rule pattern returns 0 MCCs | Return empty mcc_codes | Pipeline continues, may fail downstream if MCC required |

**Error responses in step:**

```python
if classifier is None:
    return {
        "mcc_classified": False,
        "error": "classifier_unavailable",
        "mcc_codes": [],
    }

if tenant_id not in allowed_tenants:
    return {
        "mcc_classified": False,
        "error": "tenant_not_found",
        "mcc_codes": [],
    }
```

## Testing Strategy

| Layer | What to Test | Approach |
|-------|-------------|----------|
| **Unit** | ClassificationResult creation; factory routing; pattern matching | Mock ILlmProvider, MccRepository; parameterized tests for each classifier |
| **Unit** | Repository tenant filtering | Mock AsyncSession; verify WHERE clause includes tenant_id |
| **Integration** | Classifier e2e with real DB; rule loading; demo topic bootstrap | Transactional test fixtures; temp YAML files for rules |
| **Integration** | Tenant isolation (no cross-tenant leaks) | Create merchants in tenant A, query from tenant B, verify 0 results |
| **E2E** | Full pipeline with each classifier type | Hit API endpoint with X-Tenant-ID header; verify correct classifier used |
| **E2E** | Migration (data integrity after tenant_id backfill) | Run migration; query pre-migration data as tenant="default"; expect same results |

## Migration / Rollout

**Phase 1 deployment:**
1. Deploy code with tenant_id columns added but queries NOT scoped (backward-compat mode)
2. Run Alembic migration (adds columns, backfills "default", updates constraints)
3. Flip CLASSIFIER_TYPE env var to "llm" (no change in behavior, but code uses factory)
4. Monitor metrics: classification latency, error rate (should be identical)

**Phase 2 (next minor version):**
1. Flip CLASSIFIER_TYPE to "rules" or "lookup" per deployment intent
2. Deploy rule files alongside code
3. Monitor accuracy / coverage; roll back to "llm" if issues

**Rollback:**
- **Code:** Revert env var CLASSIFIER_TYPE to "llm" and redeploy (no schema change)
- **Data:** Migration is reversible via Alembic; downgrade removes tenant_id columns (existing rows remain queryable without tenant scoping)
- **Rules:** Delete rule YAML files; system falls back to lookup or LLM

## Open Questions

- [ ] How does tenant_id flow from API layer? Via header (X-Tenant-ID) or JWT claim?
- [ ] Are there domain-specific rules (e.g., FARMACIA rules differ by country)? If yes, should tenant_id include region code?
- [ ] Should classifier selection be per-tenant or global? (Current design: global via env var; could extend to per-tenant config later)
- [ ] Rule caching policy: LRU size, TTL, invalidation on file change? (Proposal: 100 tenants, no TTL, requires restart for updates)
- [ ] Performance: Do we need composite indexes (tenant_id, code) beyond single-column index? (Defer to monitoring post-MVP)
- [ ] Backward compatibility: Should we deprecate global MCC endpoints in favor of tenant-scoped ones? (Phase 2)
