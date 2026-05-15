# Task Breakdown: Configurable Classification System

**Change Name:** configurable-classification  
**Project:** payments-mcc-classification  
**Date:** 2026-05-15  
**Status:** Ready for implementation (Phase: sdd-tasks)

---

## Review Workload Forecast

| Metric | Value | Notes |
|--------|-------|-------|
| **Estimated Changed Lines** | ~1,030 | Includes new module, migration, tests, model updates |
| **Files Created** | 8 | Classifiers (5), migration (1), demo config (1), demo loader (1) |
| **Files Modified** | 10 | Models, config, repositories (4), pipeline step, test fixtures |
| **400-Line Budget Risk** | **HIGH** | Exceeds threshold; structural refactor affecting core layers |
| **Chained PRs Recommended** | **Yes** | Recommend 2-3 stacked PRs: (1) Schema + Foundation, (2) Classifiers + Pipeline, (3) Integration + Tests |
| **Decision Needed Before Apply** | **Yes** | Delivery strategy: chained PRs vs. single `size:exception` PR required before implementation begins |
| **Parallel Work Possible** | Yes (bounded) | Phase 2b (3 classifier implementations) can run in parallel after base + factory |

---

## Task Checklist

### Phase 0: Foundation & Types (Sequential)

**Prerequisites:** None  
**Blocks:** All phases  
**Effort:** ~100 lines | ~2 hours  

- [x] **T-CC-001** Define exception hierarchy  
  **File:** `app/services/classifiers/exceptions.py`  
  **Action:** Create new file defining ClassificationError, TenantNotFoundError, InvalidClassifierTypeError, UnauthorizedTenantAccessError, ClassificationServiceError, ConfigurationError, RuleLoadError  
  **REQ:** REQ-CC-013  
  **Details:** All exceptions inherit from a base ClassificationException; include tenant_id tracking  

- [x] **T-CC-002** Define ClassificationResult dataclass  
  **File:** `app/services/classifiers/base.py` (partial)  
  **Action:** Create dataclass with fields: category, confidence, classifier_type, reasoning, metadata  
  **REQ:** REQ-CC-002  
  **Validation:** confidence ∈ [0.0, 1.0]; classifier_type ∈ ["llm", "rules", "lookup"]; category non-empty  

- [x] **T-CC-003** Define IClassifier ABC interface  
  **File:** `app/services/classifiers/base.py` (complete)  
  **Action:** Create abstract base class with async classify(merchant_name: str, tenant_id: str) → ClassificationResult  
  **REQ:** REQ-CC-001  
  **Details:** Include docstring with tenant isolation contract; define tenant validation logic  

- [x] **T-CC-004** Add configuration settings class  
  **File:** `app/core/config.py`  
  **Action:** Add Settings fields: CLASSIFIER_TYPE (default "llm"), CLASSIFIER_RULES_PATH, DEFAULT_TENANT (default "default"), DEMO_TOPICS (default True)  
  **REQ:** REQ-CC-009  
  **Validation:** Validate CLASSIFIER_RULES_PATH exists if CLASSIFIER_TYPE="rules"; raise ConfigurationError on invalid  
  **Note:** Append to existing Settings; no breaking changes  

---

### Phase 1: Database Migration (Sequential)

**Prerequisites:** Phase 0 (config values available)  
**Blocks:** Classifier implementations, repository changes  
**Effort:** ~80 lines | ~3 hours  

- [x] **T-CC-005** Create Alembic migration script  
  **File:** `app/migrations/versions/003_add_tenant_isolation.py`  
  **Action:** Write migration with 5 steps: (1) add tenant_id columns (nullable), (2) backfill to 'default', (3) set NOT NULL, (4) create indexes, (5) create composite unique constraints  
  **REQ:** REQ-CC-008  
  **Tables:** merchants, categories, mccs, validation_rules  
  **Downgrade:** Fully reversible; drop constraints, drop indexes, drop columns  
  **Downtime:** < 1 minute  

- [x] **T-CC-006** Update model definitions (add tenant_id fields)  
  **File:** `app/models/mcc.py`, `app/models/merchant.py`, `app/models/category.py` (if exists)  
  **Action:** Add tenant_id: str = Field(...) to Mcc, Merchant, Category models; set nullable=False, default="default" in ORM  
  **REQ:** REQ-CC-008  
  **Note:** Must run AFTER migration; models reflect final schema (non-nullable)  

---

### Phase 2: Classifier Module (Partially Parallel)

#### Phase 2a: Base & Factory (Sequential, unblocks 2b)

**Prerequisites:** Phase 0, Phase 1 (database ready)  
**Blocks:** Phase 2b (classifier implementations)  
**Effort:** ~150 lines | ~3 hours  

- [x] **T-CC-007** Create ClassifierFactory singleton  
  **File:** `app/services/classifiers/factory.py`  
  **Action:** Implement factory that reads CLASSIFIER_TYPE env var, instantiates LLMClassifier/RuleBasedClassifier/LookupTableClassifier, caches instance  
  **REQ:** REQ-CC-003  
  **Behavior:** Raise InvalidClassifierTypeError if type unsupported; guarantee singleton via class-level cache  
  **Testing:** Unit test: factory returns correct type per env var; subsequent calls return same instance  

#### Phase 2b: Classifier Implementations (3 tasks, can run in parallel after 2a)

**Prerequisites:** Phase 0, Phase 1, Phase 2a  
**Blocks:** Phase 3 (pipeline refactor)  
**Effort (total):** ~250 lines | ~6 hours  
**Parallelization:** All 3 can run in parallel (isolated implementations, no shared state)  

- [x] **T-CC-008** Implement LLMClassifier  
  **File:** `app/services/classifiers/llm.py`  
  **Action:** Wrap existing OpenAI integration; inherit IClassifier; call OpenAI API, retrieve tenant-scoped categories from database, return ClassificationResult with classifier_type="llm"  
  **REQ:** REQ-CC-004  
  **Details:** Reuse existing LlmProvider; add tenant_id filtering to category queries  
  **Error Handling:** Catch OpenAI timeouts/failures → raise ClassificationServiceError  
  **Testing:** Unit test with mocked OpenAI; integration test with real DB, tenant isolation verified  

- [x] **T-CC-009** Implement RuleBasedClassifier  
  **File:** `app/services/classifiers/rules.py`  
  **Action:** Load YAML rules from CLASSIFIER_RULES_PATH, parse by tenant_id, match merchant_name against patterns (case-insensitive substring), return matching category + confidence=1.0 or default "OTROS" + confidence=0.0  
  **REQ:** REQ-CC-005  
  **Details:** Lazy load + LRU cache (100 tenants, no TTL); YAML schema: `{tenant_id: {rules: [{pattern, category, mcc_codes}]}}`  
  **Error Handling:** Log invalid YAML syntax; skip malformed rules; continue processing  
  **Testing:** Unit test: rule matching, caching; integration test: multi-tenant rule isolation  

- [x] **T-CC-010** Implement LookupTableClassifier  
  **File:** `app/services/classifiers/lookup.py`  
  **Action:** Query Mcc table filtered by tenant_id; if MCC found, return associated category + confidence=1.0; else return default + confidence=0.0; implement IClassifier interface  
  **REQ:** REQ-CC-006  
  **Note:** MVP non-critical; placeholder for extensibility; minimal logic  
  **Testing:** Unit test: mock Mcc repository; integration test: MCC lookup with tenant scoping  

---

### Phase 3: Pipeline Refactor (Sequential after 2a)

**Prerequisites:** Phase 0, Phase 1, Phase 2a (factory ready)  
**Blocks:** Phase 4 (repository scoping)  
**Effort:** ~50 lines | ~2 hours  

- [x] **T-CC-011** Rename MccClassificationStep → TopicClassificationStep  
  **File:** `app/pipeline/auto_creation/mcc_classification.py`  
  **Action:** Rename class, update docstring; refactor __call__ to: (1) extract tenant_id from context (default DEFAULT_TENANT), (2) instantiate classifier via ClassifierFactory.get_classifier(), (3) call classifier.classify(merchant_name, tenant_id), (4) store result in context  
  **REQ:** REQ-CC-011, REQ-CC-012  
  **Details:** Support backward compat alias: MccClassificationStep = TopicClassificationStep  
  **Testing:** Unit test: factory called, classifier invoked with correct tenant_id; integration test: pipeline executes end-to-end per classifier type  

---

### Phase 4: Repository Tenant Isolation (Sequential after 3)

**Prerequisites:** Phase 0, Phase 1, Phase 3  
**Blocks:** Phase 5 (demo loader uses repositories)  
**Effort:** ~100 lines | ~4 hours  

- [x] **T-CC-012** Add tenant_id filtering to MccRepository  
  **File:** `app/repositories/mcc_repository.py`  
  **Action:** Add tenant_id parameter to all query methods: get_by_code, get_all, find_by_name, etc.; add WHERE clause filtering `and_(Mcc.tenant_id == tenant_id, Mcc.deleted_at.is_(None))`  
  **REQ:** REQ-CC-007  
  **Error Handling:** Raise UnauthorizedTenantAccessError if attempting cross-tenant access  
  **Testing:** Unit test: queries return only matching tenant rows; integration test: verify cross-tenant isolation  

- [x] **T-CC-013** Add tenant_id filtering to CategoryRepository  
  **File:** `app/repositories/category_repository.py`  
  **Action:** Add tenant_id parameter to all query methods; add WHERE clause filtering by tenant_id; raise UnauthorizedTenantAccessError on cross-tenant access  
  **REQ:** REQ-CC-007  
  **Testing:** Unit test: category filtering; integration test: tenant isolation  

- [x] **T-CC-014** Add tenant_id filtering to MerchantRepository  
  **File:** `app/repositories/merchant_repository.py`  
  **Action:** Add tenant_id parameter; filter all queries by tenant_id; enforce UnauthorizedTenantAccessError  
  **REQ:** REQ-CC-007  
  **Testing:** Unit test; integration test  

- [x] **T-CC-015** Add tenant_id filtering to remaining repositories (EmbeddingRepository, ValidationRuleRepository if exists)  
  **File:** `app/repositories/*.py` (all query-bearing repos)  
  **Action:** Apply same pattern: tenant_id parameter, WHERE clause filtering  
  **REQ:** REQ-CC-007  

---

### Phase 5: Demo Topics & Config (Sequential after 4)

**Prerequisites:** Phase 0, Phase 1, Phase 2a, Phase 4  
**Blocks:** Phase 6 (tests), deployment  
**Effort:** ~60 lines | ~2 hours  

- [x] **T-CC-016** Create demo_topics.yaml configuration file  
  **File:** `config/demo_topics.yaml`  
  **Action:** YAML file defining 5 default categories (FARMACIA, SUPERMERCADO, RESTAURANTE, SERVICIOS, OTROS) with descriptions and MCC codes for tenant="default"  
  **REQ:** REQ-CC-010  
  **Schema:** `{default: {categories: [{name, description, mcc_codes: []}]}}`  

- [x] **T-CC-017** Implement demo topics loader  
  **File:** `app/services/classifiers/demo_loader.py` (or `app/startup/demo_loader.py`)  
  **Action:** Boot-time loader (called from app.on_event("startup")); reads config/demo_topics.yaml, creates categories for DEFAULT_TENANT; idempotent (skip if exists)  
  **REQ:** REQ-CC-010  
  **Behavior:** Only runs if DEMO_TOPICS=True; database transaction (all-or-nothing); log each created category  
  **Testing:** Integration test: verify demo categories created on startup; idempotency test: run twice, no duplicates  

---

### Phase 6: Comprehensive Tests (Parallel after relevant phases)

**Prerequisites:** Vary by test  
**Blocks:** None (final validation)  
**Effort:** ~300 lines | ~6 hours  

- [ ] **T-CC-018** Unit tests: ClassificationResult & exceptions  
  **File:** `tests/unit/services/test_classifiers_base.py`  
  **Action:** Test ClassificationResult validation (confidence bounds, classifier_type enum, non-empty category); test exception creation and tenant_id tracking  
  **REQ:** REQ-CC-002, REQ-CC-013  

- [ ] **T-CC-019** Unit tests: ClassifierFactory  
  **File:** `tests/unit/services/test_factory.py`  
  **Action:** Test factory routing per CLASSIFIER_TYPE env var; test singleton caching; test InvalidClassifierTypeError on unsupported type  
  **REQ:** REQ-CC-003  

- [ ] **T-CC-020** Unit tests: LLMClassifier  
  **File:** `tests/unit/services/test_llm_classifier.py`  
  **Action:** Mock OpenAI client and CategoryRepository; test classify() with valid merchant → returns ClassificationResult with classifier_type="llm"; test ClassificationServiceError on API failure  
  **REQ:** REQ-CC-004  

- [ ] **T-CC-021** Unit tests: RuleBasedClassifier  
  **File:** `tests/unit/services/test_rules_classifier.py`  
  **Action:** Test rule matching (case-insensitive substring), caching, tenant-specific rule loading, default fallback, TenantNotFoundError if rules absent  
  **REQ:** REQ-CC-005  

- [ ] **T-CC-022** Unit tests: LookupTableClassifier  
  **File:** `tests/unit/services/test_lookup_classifier.py`  
  **Action:** Mock MccRepository; test MCC found → returns ClassificationResult with classifier_type="lookup"; test MCC not found → returns default  
  **REQ:** REQ-CC-006  

- [ ] **T-CC-023** Integration tests: Repository tenant isolation  
  **File:** `tests/integration/test_repository_tenant_isolation.py`  
  **Action:** Real DB; create merchants/categories/MCCs for two tenants; verify queries return only matching tenant; verify UnauthorizedTenantAccessError on cross-tenant access  
  **REQ:** REQ-CC-007  

- [ ] **T-CC-024** Integration test: TopicClassificationStep end-to-end  
  **File:** `tests/integration/test_topic_classification_step.py`  
  **Action:** Full pipeline per classifier type (LLM, rules, lookup); verify correct classifier invoked, tenant_id respected, result stored in context  
  **REQ:** REQ-CC-011  

- [ ] **T-CC-025** Integration test: Demo topics loader idempotency  
  **File:** `tests/integration/test_demo_loader.py`  
  **Action:** Load demo_topics.yaml twice; verify 5 categories created once, no duplicates  
  **REQ:** REQ-CC-010  

- [ ] **T-CC-026** Backward compatibility tests  
  **File:** `tests/integration/test_backward_compat.py`  
  **Action:** Verify existing tests pass; single-tenant queries work without explicit tenant_id; CLASSIFIER_TYPE defaults to "llm"; behavior identical to pre-upgrade  
  **REQ:** REQ-CC-012  

---

## Implementation Notes

### Dependency Graph

```
Phase 0: Foundation
    ├─→ Phase 1: Database Migration
    │       ├─→ Phase 2a: Factory (+ base IClassifier)
    │       │       ├─→ Phase 2b: LLMClassifier (parallel: Rules, Lookup)
    │       │       │       └─→ Phase 3: TopicClassificationStep rename
    │       │       │           └─→ Phase 4: Repository tenant isolation
    │       │       │               └─→ Phase 5: Demo loader
    │       │       │                   └─→ Phase 6: Tests (parallel with 2b)
```

### Critical Path

The longest sequential chain is:
Phase 0 (2h) → Phase 1 (3h) → Phase 2a (3h) → Phase 2b (6h, serialized) → Phase 3 (2h) → Phase 4 (4h) → Phase 5 (2h) = **22 hours**.

**Parallelization opportunity:** Phase 2b (3 classifiers) can run in parallel (6 hours → potential ~2 hours if 3 developers); Phase 6 (tests) can start after 2a (doesn't block anything). Realistic parallel: ~18 hours with 2-3 developers.

### Delivery Strategy (Decision Required)

Before `sdd-apply` begins, choose ONE:

1. **Chained/Stacked PRs (Recommended)**
   - PR 1: Phases 0-1 (Foundation + Migration) — ~150 lines, straightforward
   - PR 2: Phases 2a-2b (Classifier module + Factory) — ~350 lines, architectural core
   - PR 3: Phases 3-5 (Pipeline + Repos + Demo) — ~210 lines, integrations
   - PR 4: Phase 6 (Tests) — ~300 lines, validation
   - **Benefit:** Smaller reviews, easier rollback, clear separation of concerns

2. **Single PR with `size:exception` label**
   - All phases in one PR (~1030 lines)
   - Requires explicit maintainer approval and `size:exception` tag
   - Higher risk of review fatigue and conflicts

### Notes for Implementer

- **Tenant context:** Assume tenant_id flows via PipelineContext dict (existing pattern). See Phase 3 for how TopicClassificationStep extracts and uses it.
- **Backward compat:** All existing code continues to assume tenant_id="default"; new deployments can override via env var.
- **No breaking changes:** Models get new field; repositories get new parameter; old queries still work (with default tenant).
- **Testing:** Each phase should include unit tests; integration tests should be grouped in Phase 6 to avoid duplication.

---

## Success Criteria (Exit Checklist)

After all tasks complete, verify:

- [ ] All 26 tasks have a completed checkbox (or documented skip reason)
- [ ] IClassifier interface defines classification contract; all tests pass
- [ ] LLMClassifier preserves existing behavior (same MCC classifications as before)
- [ ] RuleBasedClassifier loads and applies YAML rules; pattern matching works end-to-end
- [ ] Tenant isolation: queries filtered by tenant_id; cross-tenant data never leaks
- [ ] Migration: database runs and can be reversed; no failed deployments
- [ ] Config-driven selection: CLASSIFIER_TYPE env var switches strategies without code changes
- [ ] Demo topics load on startup; default tenant has all 5 categories
- [ ] Backward compatibility: existing single-tenant deployments unchanged
- [ ] No regressions: existing test suite passes; new tests cover all new code
