# Exploration: configurable-classification

## Status
done

## Change Request
Make the payments-mcc-classification system fully agnostic and configurable so any business can use it as an open-source solution to classify their payments into configurable topics/categories.

**User flow**: Payment (merchant + amount) → MCC lookup → category classification → custom rules → ACCEPTED/REJECTED
**Example**: Payment at FARMATODO → MCC lookup → classified as FARMACIA → rules engine → ACCEPTED/REJECTED

---

## Architecture Overview

FastAPI microservice with a **7-step auto-creation pipeline** + 3-step validation pipeline.
Stack: Python / FastAPI / SQLAlchemy (async) / PostgreSQL + pgvector / structlog / outbox pattern / HMAC auth.

**Pipeline flow**:
1. Check existence
2. LLM research (Tavily)
3. Embedding generation
4. Google Places lookup
5. **MCC classification** (OpenAI LLM) ← key step
6. Merchant creation
7. Notify downstream (Pomelo)

The system is well-structured with a clean pipeline engine, dependency injection, and repository pattern. The work is primarily **configuration and decoupling**, not architectural overhaul.

---

## Hardcoded vs Configurable

| Aspect | Current State | Needed |
|--------|--------------|--------|
| MCC classifier | OpenAI LLM only | Pluggable: LLM, rule-based, lookup table |
| Categories/Topics | CRUD via API, no defaults | Per-tenant topics + demo defaults |
| Validation rules | Hard-coded in `ValidateNameStep` | Config-driven, customizable |
| Rules engine | **Does not exist** | ACCEPTED/REJECTED evaluator |
| Tenant isolation | None (single schema) | Row-level `tenant_id` filtering |
| Training/Eval | **Does not exist** | Labeled dataset + metrics pipeline |
| Domain config | Not supported | YAML/JSON per-business config files |

---

## MCC → Category Mapping

Current flow:
```
merchant name → LLM (OpenAI) → MCC codes (standard, e.g. "5411") → DB verify → MerchantMcc join table → category via MCC.category_id
```

**Problem**: No way to customize classification strategy or category taxonomy per business.

---

## Rules Engine

**Does not exist.** `MerchantMetadata` has unused fields (`reason`, `mcc_association_type`) that suggest planned support, but no evaluation engine is implemented.

---

## Eval / Training Data Pipeline

**Does not exist.** Tests use mocks only. No labeled dataset infrastructure, train/test splits, or accuracy metrics.

---

## Key Files

| File | Role | Hardcoding |
|------|------|-----------|
| `app/pipeline/auto_creation/mcc_classification.py` | Step 5: LLM-based MCC classification | LLM call only |
| `app/models/mcc.py` | MCC + Category schema | Global codes, no tenant_id |
| `app/services/mcc_service.py` | MCC CRUD + embeddings | No classifier abstraction |
| `app/pipeline/validation/validate_name.py` | Validation rules | Hard-coded length/char rules |
| `app/models/merchant.py` | Merchant entity | No tenant isolation |
| `app/core/config.py` | Settings | No domain/topic/rule config |

---

## Approaches Considered

| Approach | Scope | Effort | Pros | Cons |
|----------|-------|--------|------|------|
| **Minimal Tenant** | Add tenant_id; API-created topics; keep LLM-only; config-driven validation | Low | No breaking changes | No alternative classifiers; no rules engine |
| **Classifier Abstraction** ✅ | IClassifier interface; LLM + rule-based + lookup; tenant topics; config-driven | Medium | Future-proof; clear extension points | No rules engine yet |
| **Full Config + Rules** | Classifier Abstraction + rules engine + training/eval + domain config files | High | Complete solution | More complexity for Phase 1 |

---

## Recommended Approach: Classifier Abstraction (Phase 1)

1. Create `IClassifier` interface + factory (`LLMClassifier`, `RuleBasedClassifier`)
2. Add `tenant_id` to merchants/mccs/categories (row-level filtering)
3. Rename `MccClassificationStep` → `TopicClassificationStep`
4. Config-driven classifier selection (env var or YAML)
5. YAML-based rule classifier for simple pattern matching
6. Ship demo default topics (FARMACIA, SUPERMERCADO, RESTAURANTE, etc.)

**Phase 2 (later)**: Full rules engine (DSL + evaluator) + training/eval pipeline

---

## Risks & Open Questions

1. **Tenant model**: Row-level filtering is recommended for Phase 1; schema-per-tenant if needed later
2. **MCCs vs Topics**: MCCs stay global (standard codes); topics are per-tenant
3. **Rules DSL complexity**: Keep MVP as YAML; evolve to JSON Schema or CEL later
4. **Migration burden**: Existing merchants/MCCs/categories need tenant_id backfill
5. **Training data source**: CSV for MVP; API uploads + LLM-synthetic generation later

---

## Success Criteria (Phase 1)

- **Tenant A** configures 15 custom topics, classifies with LLM
- **Tenant B** uses rule-based classifier (if seller_name contains "Amazon" → MARKETPLACE)
- **Tenant C** uses LLM classification, sees demo default topics pre-loaded
- Any deployer can ship their own `topics.yaml` with zero code changes
