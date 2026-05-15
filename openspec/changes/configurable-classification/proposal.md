# Proposal: Configurable Classification System

## Intent

The payments-mcc-classification microservice is currently hardcoded for a single classification strategy (OpenAI LLM) and a single global taxonomy (Categories). To make this system an open-source, multi-tenant solution that any business can deploy and customize, we must:

1. **Decouple the classifier strategy** from the pipeline (support LLM, rule-based, and lookup-table classifiers)
2. **Add tenant isolation** so each deployment has its own categories, MCCs, and validation rules
3. **Enable configuration-driven deployment** via YAML or environment variables (no code changes to add a classifier or custom rule)

This transforms the service from a locked, single-strategy system into a flexible, deployable platform.

## Scope

### In Scope (Phase 1: Classifier Abstraction)
- **IClassifier interface** + factory pattern supporting LLMClassifier, RuleBasedClassifier, LookupTableClassifier
- **Tenant isolation** via row-level tenant_id filtering on merchants, categories, MCCs
- **Rename MccClassificationStep → TopicClassificationStep** to reflect configuration-agnostic behavior
- **YAML-based rule classifier** for pattern matching (e.g., "if name contains FARMA → FARMACIA")
- **Config-driven classifier selection** via env var or YAML (`CLASSIFIER_TYPE=llm|rules|lookup`)
- **Demo defaults** (out-of-box topics: FARMACIA, SUPERMERCADO, RESTAURANTE, SERVICIOS, OTROS)
- **Database schema migration** to add tenant_id to merchants, mccs, categories, validation_rules
- **Backward compatibility** mode for existing single-tenant deployments (default tenant = "default")

### Out of Scope (Phase 2+)
- **Full Rules DSL** (currently YAML key-value only; Phase 2 adds complex boolean logic)
- **Rules engine evaluator** (ACCEPTED/REJECTED decision logic for payment transactions)
- **Training/evaluation pipeline** (labeled dataset + metrics for classifier performance)
- **Dynamic schema-per-tenant** (row-level filtering first; schema separation if needed post-MVP)
- **UI for rule builder** (manual YAML editing in Phase 1)
- **Multi-strategy ensemble** (combining multiple classifiers; Phase 2+)

## Capabilities

### New Capabilities
- `classifier-strategy`: Abstracted classifier interface allowing pluggable LLM, rule, and lookup-table strategies
- `tenant-isolation`: Row-level tenant_id filtering for merchants, categories, MCCs, and validation rules
- `topic-classification`: Renamed, configuration-agnostic classification step replacing MccClassificationStep
- `rule-based-classifier`: YAML-based pattern classifier for out-of-box rule support (Phase 1 MVP)
- `default-taxonomy`: Pre-loaded demo categories and topic mappings shipped with the service

### Modified Capabilities
- `merchant-validation`: Validation rules now tenant-scoped and configuration-driven (not hard-coded)

## Approach

### 1. Create IClassifier Interface
```python
# app/services/classifiers/base.py
class IClassifier(ABC):
    async def classify(self, merchant_name: str, tenant_id: str) -> ClassificationResult:
        """Classify merchant name into a topic/category."""
        pass
```

### 2. Factory + Concrete Implementations
- **LLMClassifier**: Uses OpenAI (current behavior)
- **RuleBasedClassifier**: Loads tenant-specific rules from `categories/{tenant_id}/rules.yaml`
- **LookupTableClassifier**: Direct MCC/category lookup without inference

### 3. Add Tenant ID to Core Schemas
- `Merchant.tenant_id` (String, indexed, defaults to "default")
- `Category.tenant_id` (String, indexed)
- `Mcc.tenant_id` (String, nullable, for per-tenant MCC overrides)
- `ValidationRule.tenant_id` (String, indexed)

### 4. Config-Driven Classifier Selection
```yaml
# config.yaml or env
CLASSIFIER_TYPE: "rules"  # or "llm", "lookup"
CLASSIFIER_RULES_PATH: "/config/rules"
DEFAULT_TENANT: "default"
DEMO_TOPICS: true  # auto-load demo categories on startup
```

### 5. Demo Default Topics (YAML)
```yaml
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

### 6. Migrate Existing Data
1. Add `tenant_id` column with default "default"
2. Backfill existing rows with tenant_id = "default"
3. No rows deleted; backward-compatible migration
4. Add unique constraints: (code, tenant_id) for Mcc, (name, tenant_id) for Category

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `app/services/classifiers/` | New | IClassifier interface + LLMClassifier, RuleBasedClassifier, LookupTableClassifier |
| `app/pipeline/auto_creation/mcc_classification.py` | Modified | Rename to TopicClassificationStep, inject classifier via factory |
| `app/models/mcc.py` | Modified | Add tenant_id to Category, Mcc, add new ValidationRule model |
| `app/models/merchant.py` | Modified | Add tenant_id column, update queries to filter by tenant |
| `app/core/config.py` | Modified | Add CLASSIFIER_TYPE, CLASSIFIER_RULES_PATH, DEFAULT_TENANT settings |
| `app/repositories/` | Modified | All queries now tenant-scoped (mcc_repo, category_repo, merchant_repo) |
| `app/migrations/` | New | Alembic migration: add tenant_id columns, backfill "default", add unique constraints |
| `config/demo_topics.yaml` | New | Default categories and MCC mappings (shipped with service) |

## Migration Plan

### Database
1. **Create migration** `add_tenant_isolation.py`:
   - Add `tenant_id VARCHAR(100)` to merchants, categories, mccs (NOT NULL, default "default")
   - Add `tenant_id VARCHAR(100)` to validation_rules (nullable initially)
   - Create indexes on (table, tenant_id)
   - Add unique constraints: (code, tenant_id) on mccs, (name, tenant_id) on categories
   - Backfill: `UPDATE merchants SET tenant_id = 'default' WHERE tenant_id IS NULL`

2. **Downtime**: < 1 minute (backfill is fast, no dependency changes)

### Application
1. Inject classifier via factory in MccClassificationStep.__init__
2. Update all repo queries to filter by context.tenant_id (default "default")
3. Deprecate global Category/Mcc endpoints; phase out in next minor version
4. Existing deployments run with CLASSIFIER_TYPE=llm, DEFAULT_TENANT=default (no behavior change)

### Rollback
1. If CLASSIFIER_TYPE deployment fails: revert env var to "llm"
2. If migration fails: rollback Alembic migration; existing rows remain queryable without tenant_id filter
3. No code rollback needed if classifier selection fails at runtime (factory pattern isolates failure)

## Dependencies

- **Alembic** (existing): Handle tenant_id migration
- **SQLAlchemy async session**: Context propagation for tenant_id (already in place)
- **OpenAI SDK** (existing): LLMClassifier uses same provider
- **PyYAML**: Rule-based classifier config parsing

## Success Criteria

- [ ] IClassifier interface defines classification contract; all tests pass
- [ ] LLMClassifier preserves existing behavior (same MCC classifications as before)
- [ ] RuleBasedClassifier can load and apply YAML rules; simple pattern matching works end-to-end
- [ ] Tenant isolation: queries filtered by tenant_id; cross-tenant data never leaks
- [ ] Migration: database runs with and without tenant_id backfill (no failed deployments)
- [ ] Config-driven selection: CLASSIFIER_TYPE env var switches between strategies without code change
- [ ] Demo topics load on startup; default tenant has FARMACIA, SUPERMERCADO, RESTAURANTE, SERVICIOS, OTROS
- [ ] Backward compatibility: existing single-tenant deployments work unchanged (CLASSIFIER_TYPE defaults to "llm", DEFAULT_TENANT="default")
- [ ] No regressions: existing test suite passes; new tests cover classifier factory and tenant isolation
