"""Rule-based merchant classifier using YAML rules."""

import os
from typing import Optional, Dict, List, Any
from functools import lru_cache
import yaml
import structlog
from app.services.classifiers.base import IClassifier, ClassificationResult
from app.services.classifiers.exceptions import (
    TenantNotFoundError,
    ClassificationError,
    RuleLoadError,
)

logger = structlog.get_logger(__name__)


class RuleBasedClassifier(IClassifier):
    """Rule-based classifier that matches merchant names against YAML rules.

    Rules are loaded from YAML files organized by tenant_id.
    Implements LRU caching for performance (max 100 tenants).
    """

    def __init__(self, rules_path: str):
        """Initialize with rules directory path."""
        self._rules_path = rules_path
        if not os.path.isdir(rules_path):
            raise ValueError(f"Rules path does not exist or is not a directory: {rules_path}")

    @lru_cache(maxsize=100)
    def _load_rules(self, tenant_id: str) -> Dict[str, Any]:
        """Load and cache rules for a tenant.

        Args:
            tenant_id: Tenant identifier

        Returns:
            Dictionary with rules for the tenant

        Raises:
            RuleLoadError: If rules cannot be loaded or parsed
        """
        # Construct path to tenant's rules file
        rules_file = os.path.join(self._rules_path, f"{tenant_id}_rules.yaml")

        if not os.path.exists(rules_file):
            raise RuleLoadError(
                rules_file,
                f"Rules file not found for tenant '{tenant_id}'",
            )

        try:
            with open(rules_file, "r") as f:
                rules = yaml.safe_load(f)
                if not rules:
                    rules = {"rules": []}
                return rules
        except yaml.YAMLError as e:
            raise RuleLoadError(
                rules_file,
                f"Invalid YAML syntax: {str(e)}",
            )
        except Exception as e:
            raise RuleLoadError(
                rules_file,
                f"Failed to read file: {str(e)}",
            )

    async def classify(
        self,
        merchant_name: str,
        tenant_id: str,
        description: Optional[str] = None,
    ) -> ClassificationResult:
        """
        Classify a merchant using rule-based matching.

        Matches merchant_name against patterns (case-insensitive substring).
        Returns first matching rule with confidence=1.0, or default with confidence=0.0.

        Args:
            merchant_name: Name of the merchant
            tenant_id: Tenant context for rule scoping
            description: Optional merchant description (not used in rule matching)

        Returns:
            ClassificationResult with matched category or default

        Raises:
            ClassificationError: If input is invalid
            TenantNotFoundError: If tenant has no rules
        """
        # Input validation
        if not merchant_name or not isinstance(merchant_name, str):
            raise ClassificationError("merchant_name cannot be empty")

        if not tenant_id or not isinstance(tenant_id, str):
            raise ClassificationError("tenant_id cannot be empty")

        # Load rules for tenant
        try:
            rules_data = self._load_rules(tenant_id)
        except RuleLoadError:
            raise TenantNotFoundError(tenant_id)

        rules = rules_data.get("rules", [])
        if not rules:
            logger.warning(
                "No rules defined for tenant",
                tenant_id=tenant_id,
                merchant_name=merchant_name,
            )
            raise TenantNotFoundError(tenant_id)

        # Normalize merchant name for matching
        normalized_name = merchant_name.upper()

        # Match against rules
        for rule in rules:
            try:
                pattern = rule.get("pattern", "").upper()
                category = rule.get("category", "OTROS")
                match_type = rule.get("match", "contains")

                if self._match_pattern(normalized_name, pattern, match_type):
                    logger.info(
                        "Rule matched for merchant",
                        merchant_name=merchant_name,
                        category=category,
                        pattern=pattern,
                        tenant_id=tenant_id,
                    )
                    return ClassificationResult(
                        category=category,
                        confidence=1.0,
                        classifier_type="rules",
                        reasoning=f"Matched rule pattern '{pattern}'",
                        metadata={
                            "merchant_name": merchant_name,
                            "tenant_id": tenant_id,
                            "matched_pattern": pattern,
                        },
                    )
            except Exception as e:
                logger.warning(
                    "Error processing rule",
                    error=str(e),
                    rule=rule,
                    tenant_id=tenant_id,
                )
                continue

        # No rule matched, return default
        logger.info(
            "No rule matched for merchant, returning default",
            merchant_name=merchant_name,
            tenant_id=tenant_id,
        )
        return ClassificationResult(
            category="OTROS",
            confidence=0.0,
            classifier_type="rules",
            reasoning="No matching rule found",
            metadata={
                "merchant_name": merchant_name,
                "tenant_id": tenant_id,
            },
        )

    @staticmethod
    def _match_pattern(text: str, pattern: str, match_type: str = "contains") -> bool:
        """Match text against pattern using specified matching strategy.

        Args:
            text: Text to match against (already uppercase)
            pattern: Pattern to match (already uppercase)
            match_type: One of "contains", "startswith", "endswith", "exact", "regex"

        Returns:
            True if pattern matches, False otherwise
        """
        if match_type == "contains":
            return pattern in text
        elif match_type == "startswith":
            return text.startswith(pattern)
        elif match_type == "endswith":
            return text.endswith(pattern)
        elif match_type == "exact":
            return text == pattern
        elif match_type == "regex":
            import re

            try:
                return bool(re.search(pattern, text))
            except re.error:
                return False
        else:
            # Default to contains
            return pattern in text
