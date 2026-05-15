# Specification: Configurable Classification System (Phase 1)

## Overview

This specification defines the requirements for Phase 1 of the configurable classification system transformation. The system must support pluggable classifier strategies (LLM, rule-based, lookup-table), add tenant isolation to all data models, and maintain backward compatibility with existing single-tenant deployments.

## Requirements

### REQ-CC-001: IClassifier Interface Contract

The system MUST define an abstract `IClassifier` interface that specifies the contract for all classifier implementations.

**Interface Signature:**
```python
class IClassifier(ABC):
    async def classify(
        self, 
        merchant_name: str, 
        tenant_id: str
    ) -> ClassificationResult:
        """Classify a merchant name into a topic/category."""
        pass
```

**Behavior:**
- The `classify()` method MUST accept merchant name (non-empty string) and tenant_id (non-empty string).
- MUST return a `ClassificationResult` object containing the assigned category and confidence score.
- MUST raise `ClassificationError` if merchant_name is empty or None.
- MUST raise `TenantNotFoundError` if tenant_id does not exist or has no categories defined.
- Classification MUST be scoped to the provided tenant_id; cross-tenant data MUST never be returned.

**Scenario: Valid merchant classification**
- GIVEN a registered tenant with categories defined
- WHEN classify() is called with a valid merchant_name and tenant_id
- THEN a ClassificationResult is returned with category name and confidence score
- AND confidence is a float between 0.0 and 1.0

**Scenario: Missing merchant name**
- GIVEN a registered tenant
- WHEN classify() is called with an empty or None merchant_name
- THEN ClassificationError is raised with message "merchant_name cannot be empty"

**Scenario: Unregistered tenant**
- GIVEN no tenant matching the provided tenant_id
- WHEN classify() is called with an unknown tenant_id
- THEN TenantNotFoundError is raised

---

### REQ-CC-002: ClassificationResult Schema

The system MUST define a `ClassificationResult` dataclass that represents the output of any classifier.

**Schema:**
```python
@dataclass
class ClassificationResult:
    category: str              # Category name (e.g., "FARMACIA")
    confidence: float          # 0.0 to 1.0
    classifier_type: str       # "llm" | "rules" | "lookup"
    reasoning: Optional[str]   # Why this category was chosen
```

**Constraints:**
- `category` MUST be non-empty.
- `confidence` MUST be >= 0.0 and <= 1.0.
- `classifier_type` MUST be one of: "llm", "rules", "lookup".
- `reasoning` MAY be None; if provided, MUST be a non-empty string.

**Scenario: Successful classification result**
- GIVEN a valid merchant classification
- WHEN ClassificationResult is created
- THEN all fields are populated and valid
- AND confidence is a valid float between 0.0 and 1.0

---

### REQ-CC-003: Classifier Factory

The system MUST provide a `ClassifierFactory` that instantiates the appropriate classifier based on configuration.

**Factory Behavior:**
- Factory MUST read the `CLASSIFIER_TYPE` environment variable (default: "llm").
- Factory MUST instantiate LLMClassifier when CLASSIFIER_TYPE="llm".
- Factory MUST instantiate RuleBasedClassifier when CLASSIFIER_TYPE="rules".
- Factory MUST instantiate LookupTableClassifier when CLASSIFIER_TYPE="lookup".
- Factory MUST raise `InvalidClassifierTypeError` if CLASSIFIER_TYPE is not one of the above.
- Factory MUST be a singleton; repeated calls return the same instance.

**Scenario: Factory selects LLMClassifier**
- GIVEN CLASSIFIER_TYPE environment variable set to "llm"
- WHEN ClassifierFactory.get_classifier() is called
- THEN an LLMClassifier instance is returned
- AND subsequent calls return the same instance

**Scenario: Factory selects RuleBasedClassifier**
- GIVEN CLASSIFIER_TYPE environment variable set to "rules"
- WHEN ClassifierFactory.get_classifier() is called
- THEN a RuleBasedClassifier instance is returned
- AND CLASSIFIER_RULES_PATH environment variable is validated (file/directory must exist)

**Scenario: Invalid classifier type**
- GIVEN CLASSIFIER_TYPE environment variable set to an unsupported value (e.g., "unknown")
- WHEN ClassifierFactory.get_classifier() is called
- THEN InvalidClassifierTypeError is raised

---

### REQ-CC-004: LLMClassifier Implementation

The system MUST provide an `LLMClassifier` that uses OpenAI's API to classify merchants, preserving existing behavior.

**Behavior:**
- LLMClassifier MUST use the same OpenAI API client and prompt structure as the current system.
- LLMClassifier MUST accept merchant_name and tenant_id and call the OpenAI API.
- LLMClassifier MUST retrieve tenant-specific categories from the database (scoped by tenant_id).
- LLMClassifier MUST return a ClassificationResult with classifier_type="llm".
- LLMClassifier MUST handle OpenAI API timeouts and failures gracefully (raise `ClassificationServiceError`).

**Scenario: Successful LLM classification**
- GIVEN a registered tenant with categories and valid OpenAI API access
- WHEN LLMClassifier.classify("Farmacia del Barrio", tenant_id) is called
- THEN a ClassificationResult is returned with category="FARMACIA" and confidence > 0.5
- AND classifier_type="llm"

**Scenario: OpenAI API failure**
- GIVEN OpenAI API is unavailable or returns an error
- WHEN LLMClassifier.classify() is called
- THEN ClassificationServiceError is raised with original API error message

---

### REQ-CC-005: RuleBasedClassifier Implementation

The system MUST provide a `RuleBasedClassifier` that applies tenant-specific YAML rules to classify merchants.

**Behavior:**
- RuleBasedClassifier MUST load rules from `CLASSIFIER_RULES_PATH` (env var) at initialization.
- Rules file format MUST be YAML, keyed by tenant_id, containing pattern-to-category mappings.
- RuleBasedClassifier MUST match merchant_name against patterns using case-insensitive substring matching.
- RuleBasedClassifier MUST return the first matching category with confidence=1.0 (exact rule match).
- RuleBasedClassifier MUST return a default category (e.g., "OTROS") if no rule matches; confidence=0.0.
- RuleBasedClassifier MUST return a ClassificationResult with classifier_type="rules".

**YAML Schema:**
```yaml
default:  # default tenant rules
  rules:
    - pattern: "farmacia"
      category: "FARMACIA"
    - pattern: "drogueria"
      category: "FARMACIA"
    - pattern: "supermercado"
      category: "SUPERMERCADO"
    - pattern: "restaurante"
      category: "RESTAURANTE"
    - pattern: "bar"
      category: "RESTAURANTE"

tenant_acme:  # custom tenant rules
  rules:
    - pattern: "pharmacy"
      category: "PHARMACY"
```

**Scenario: Rule matches merchant name**
- GIVEN RuleBasedClassifier loaded with rules for "default" tenant
- WHEN classify("Farmacia del Centro", tenant_id="default") is called
- THEN ClassificationResult is returned with category="FARMACIA", confidence=1.0
- AND classifier_type="rules"

**Scenario: No rule matches, return default**
- GIVEN RuleBasedClassifier with rules and default category="OTROS"
- WHEN classify("XYZ Corporation", tenant_id="default") is called (no matching rule)
- THEN ClassificationResult is returned with category="OTROS", confidence=0.0

**Scenario: Tenant-specific rules applied**
- GIVEN RuleBasedClassifier with rules for "tenant_acme"
- WHEN classify("Central Pharmacy", tenant_id="tenant_acme") is called
- THEN ClassificationResult is returned using "tenant_acme" rules (not "default")

---

### REQ-CC-006: LookupTableClassifier Implementation

The system MUST provide a `LookupTableClassifier` that directly maps MCC codes to categories without inference.

**Behavior:**
- LookupTableClassifier MUST query the database for Mcc records filtered by tenant_id.
- LookupTableClassifier MUST not perform any inference; if MCC code exists, return associated category.
- LookupTableClassifier MUST accept merchant_name (required by interface but not used for classification).
- LookupTableClassifier MUST return confidence=1.0 if MCC is found; confidence=0.0 if not found.
- LookupTableClassifier MUST return a ClassificationResult with classifier_type="lookup".

**Note:** LookupTableClassifier is not used in Phase 1 MVP but MUST be implemented for extensibility.

**Scenario: MCC found in lookup table**
- GIVEN a merchant with a known MCC code and LookupTableClassifier initialized
- WHEN classify(merchant_name, tenant_id) is called
- THEN ClassificationResult is returned with the MCC's category and confidence=1.0
- AND classifier_type="lookup"

---

### REQ-CC-007: Tenant Isolation via Row-Level Filtering

The system MUST enforce tenant isolation such that queries for any entity (Merchant, Category, MCC, ValidationRule) return only rows matching the provided tenant_id.

**Behavior:**
- All repository methods (MerchantRepository, CategoryRepository, MccRepository, ValidationRuleRepository) MUST accept a tenant_id parameter.
- Repository queries MUST include a WHERE clause filtering by tenant_id.
- Repository methods MUST raise `UnauthorizedTenantAccessError` if an attempt is made to access a resource with a mismatched tenant_id.
- No cross-tenant data leaks are permitted.

**Scenario: Query single tenant's merchants**
- GIVEN MerchantRepository with data from multiple tenants
- WHEN get_merchants(tenant_id="tenant_a") is called
- THEN only merchants with tenant_id="tenant_a" are returned
- AND merchants with tenant_id="tenant_b" are excluded

**Scenario: Attempt cross-tenant access**
- GIVEN a merchant with tenant_id="tenant_a"
- WHEN user attempts to update the merchant via get_merchant_by_id(id, tenant_id="tenant_b")
- THEN UnauthorizedTenantAccessError is raised

---

### REQ-CC-008: Database Schema Migration

The system MUST add tenant_id columns to all relevant tables and enforce tenant isolation at the database level.

**Migration Changes:**
- ADD `tenant_id VARCHAR(100) NOT NULL DEFAULT 'default'` to merchants table
- ADD `tenant_id VARCHAR(100) NOT NULL DEFAULT 'default'` to categories table
- ADD `tenant_id VARCHAR(100) NOT NULL DEFAULT 'default'` to mccs table
- ADD `tenant_id VARCHAR(100) DEFAULT 'default'` to validation_rules table (nullable for backward compatibility)
- CREATE INDEX ON merchants(tenant_id)
- CREATE INDEX ON categories(tenant_id)
- CREATE INDEX ON mccs(tenant_id)
- CREATE INDEX ON validation_rules(tenant_id)
- ADD UNIQUE CONSTRAINT (code, tenant_id) on mccs table
- ADD UNIQUE CONSTRAINT (name, tenant_id) on categories table
- BACKFILL all existing rows: `UPDATE {table} SET tenant_id='default' WHERE tenant_id IS NULL`

**Scenario: Migration creates tenant isolation indexes**
- GIVEN migration script is executed against the production database
- WHEN Alembic upgrade is run
- THEN all tenant_id columns are created and indexed
- AND all existing rows are backfilled with tenant_id='default'
- AND unique constraints are created

**Scenario: Downtime is minimal**
- GIVEN the migration script runs
- THEN total downtime MUST be < 1 minute
- AND no rows are deleted; migration is fully reversible

---

### REQ-CC-009: Configuration Management

The system MUST allow classifier strategy and tenant defaults to be configured via environment variables.

**Configuration Variables:**

| Variable | Type | Default | Required | Validation |
|----------|------|---------|----------|-----------|
| CLASSIFIER_TYPE | enum | "llm" | No | "llm" \| "rules" \| "lookup" |
| CLASSIFIER_RULES_PATH | string | None | Conditional | Path must exist if CLASSIFIER_TYPE="rules" |
| DEFAULT_TENANT | string | "default" | No | Non-empty string |
| DEMO_TOPICS | bool | True | No | True \| False |
| OPENAI_API_KEY | string | None | Conditional | Required if CLASSIFIER_TYPE="llm" |

**Behavior:**
- Settings MUST be loaded from environment at application startup.
- Settings MUST be validated before first classifier instantiation.
- Invalid configuration MUST raise `ConfigurationError` with detailed message.
- Demo topics MUST auto-load if DEMO_TOPICS=True (loads default categories for DEFAULT_TENANT).

**Scenario: Valid configuration loaded**
- GIVEN CLASSIFIER_TYPE="rules" and CLASSIFIER_RULES_PATH="/etc/rules.yaml"
- WHEN application starts
- THEN settings are validated and RuleBasedClassifier is instantiated successfully

**Scenario: Missing required path**
- GIVEN CLASSIFIER_TYPE="rules" but CLASSIFIER_RULES_PATH does not exist
- WHEN application starts
- THEN ConfigurationError is raised with message "CLASSIFIER_RULES_PATH file not found"

---

### REQ-CC-010: Demo Default Topics

The system MUST provide a default set of categories and MCC mappings that load automatically when DEMO_TOPICS=True.

**Demo Categories (for DEFAULT_TENANT):**
- FARMACIA: Farmacias y droguerías
- SUPERMERCADO: Supermercados y almacenes
- RESTAURANTE: Restaurantes y bares
- SERVICIOS: Servicios (plomería, electricidad, etc)
- OTROS: Otros (catchall)

**Demo YAML Schema (`config/demo_topics.yaml`):**
```yaml
default:
  categories:
    - name: FARMACIA
      description: "Farmacias y droguerías"
      mcc_codes: ["5912"]
    - name: SUPERMERCADO
      description: "Supermercados y almacenes"
      mcc_codes: ["5411", "5412"]
    - name: RESTAURANTE
      description: "Restaurantes y bares"
      mcc_codes: ["5812", "5813"]
    - name: SERVICIOS
      description: "Servicios (plomería, electricidad, etc)"
      mcc_codes: ["7623", "7631", "7641"]
    - name: OTROS
      description: "Otros"
      mcc_codes: []
```

**Behavior:**
- Demo topics MUST load into the database (DEFAULT_TENANT) on first application startup if DEMO_TOPICS=True.
- Demo topics MUST be idempotent; running twice does not create duplicates.
- Demo topics MUST only apply to DEFAULT_TENANT; multi-tenant deployments must manage their own categories.

**Scenario: Demo topics load on startup**
- GIVEN DEMO_TOPICS=True and no categories exist for default tenant
- WHEN application starts
- THEN all five demo categories are created in the database
- AND no SQL errors occur; operation is idempotent

---

### REQ-CC-011: TopicClassificationStep Renaming

The system MUST rename `MccClassificationStep` to `TopicClassificationStep` to reflect the configuration-agnostic classification process.

**Behavior:**
- TopicClassificationStep MUST accept a merchant_name and tenant_id as input.
- TopicClassificationStep MUST instantiate a classifier via ClassifierFactory.
- TopicClassificationStep MUST call classifier.classify(merchant_name, tenant_id).
- TopicClassificationStep MUST store the returned ClassificationResult in the pipeline context.
- TopicClassificationStep MUST remain agnostic to the underlying classifier strategy.
- Old MccClassificationStep name MUST be deprecated (but may remain as an alias for backward compatibility).

**Scenario: Pipeline runs with TopicClassificationStep**
- GIVEN a payment pipeline with TopicClassificationStep configured
- WHEN a merchant is processed
- THEN TopicClassificationStep calls the active classifier (LLM, rules, or lookup)
- AND the merchant receives a classification result

---

### REQ-CC-012: Backward Compatibility

The system MUST maintain full backward compatibility with existing single-tenant deployments.

**Behavior:**
- Default CLASSIFIER_TYPE MUST be "llm" (preserving existing behavior).
- Default DEFAULT_TENANT MUST be "default".
- Existing deployments with no env var configuration MUST work unchanged.
- All existing tests MUST pass without modification.
- Single-tenant queries MUST work with or without explicit tenant_id in context.

**Scenario: Existing deployment runs with defaults**
- GIVEN an existing single-tenant deployment with no configuration changes
- WHEN the application starts after the migration
- THEN CLASSIFIER_TYPE defaults to "llm"
- AND DEFAULT_TENANT defaults to "default"
- AND all existing queries filter by tenant_id="default"
- AND merchant classification behavior is identical to before

---

### REQ-CC-013: Error Handling

The system MUST define and handle classification-specific errors gracefully.

**Error Types:**

| Error | Cause | HTTP Code | Action |
|-------|-------|-----------|--------|
| ClassificationError | Invalid input (empty merchant_name) | 400 | Log and reject |
| TenantNotFoundError | Tenant_id does not exist | 404 | Log and raise to caller |
| ClassificationServiceError | External API failure (OpenAI) | 503 | Retry or fallback |
| InvalidClassifierTypeError | Invalid CLASSIFIER_TYPE config | 500 | Fail at startup |
| UnauthorizedTenantAccessError | Cross-tenant access attempt | 403 | Log and reject |
| ConfigurationError | Invalid env var or missing file | 500 | Fail at startup |

**Scenario: Handle missing tenant gracefully**
- GIVEN classify() is called with a tenant_id that does not exist
- WHEN TenantNotFoundError is raised
- THEN error is logged with tenant_id and caller context
- AND HTTP 404 is returned to the client

---

## Acceptance Scenarios (End-to-End)

### Scenario: Deploy with rule-based classifier and custom tenant

- GIVEN a new tenant "acme_corp" with custom rules in CLASSIFIER_RULES_PATH
- WHEN CLASSIFIER_TYPE="rules", CLASSIFIER_RULES_PATH="/config/acme_rules.yaml", DEFAULT_TENANT="acme_corp"
- WHEN application starts
- THEN RuleBasedClassifier is instantiated and loads acme_rules.yaml
- WHEN classify("Farmacia 24h", tenant_id="acme_corp") is called
- THEN the classification uses acme_corp rules, not demo rules
- AND result has classifier_type="rules"

### Scenario: Existing single-tenant deployment is unaffected

- GIVEN an existing production deployment with CLASSIFIER_TYPE unset
- WHEN application is updated and starts
- THEN CLASSIFIER_TYPE defaults to "llm"
- AND DEFAULT_TENANT defaults to "default"
- AND all merchants are queries with tenant_id="default"
- AND behavior is identical to pre-upgrade

### Scenario: Tenant isolation prevents cross-tenant data leaks

- GIVEN two tenants: "tenant_a" and "tenant_b"
- AND each tenant has distinct categories (FARMACIA, RESTAURANT, etc)
- WHEN MerchantRepository.get_merchants(tenant_id="tenant_a") is called
- THEN only merchants with tenant_id="tenant_a" are returned
- AND merchants in tenant_b are never visible

### Scenario: Classification result contains metadata

- GIVEN any classifier (LLM, rules, or lookup)
- WHEN classify() is called
- THEN ClassificationResult contains:
  - category (e.g., "FARMACIA")
  - confidence (float 0.0–1.0)
  - classifier_type (enum: "llm", "rules", "lookup")
  - reasoning (optional explanation)

---

## Implementation Notes

- All classifier implementations MUST be async.
- All repository queries MUST filter by tenant_id; no global queries are permitted.
- Configuration validation MUST happen at application startup, not per-request.
- Demo topics MUST be loaded in a database transaction; if any category fails to insert, the entire operation rolls back.
- LLMClassifier MUST use the same OpenAI prompt structure; classifier strategy is transparent to the API.

---

## Success Criteria (from Proposal)

- [x] IClassifier interface defines classification contract; all tests pass
- [x] LLMClassifier preserves existing behavior (same MCC classifications as before)
- [x] RuleBasedClassifier can load and apply YAML rules; simple pattern matching works end-to-end
- [x] Tenant isolation: queries filtered by tenant_id; cross-tenant data never leaks
- [x] Migration: database runs with and without tenant_id backfill (no failed deployments)
- [x] Config-driven selection: CLASSIFIER_TYPE env var switches between strategies without code change
- [x] Demo topics load on startup; default tenant has FARMACIA, SUPERMERCADO, RESTAURANTE, SERVICIOS, OTROS
- [x] Backward compatibility: existing single-tenant deployments work unchanged
- [x] No regressions: existing test suite passes; new tests cover classifier factory and tenant isolation
