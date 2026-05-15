"""Factory for instantiating classifier implementations."""

from typing import Optional
from app.core.config import settings
from app.services.classifiers.exceptions import InvalidClassifierTypeError


class ClassifierFactory:
    """Factory for creating classifier instances based on configuration.

    Implements singleton pattern; repeated calls return the same instance.
    """

    _instances: dict[str, "ClassifierFactory"] = {}
    _classifier_instances: dict[str, object] = {}

    def __new__(cls):
        """Ensure singleton instance per configuration."""
        if "default" not in cls._instances:
            cls._instances["default"] = super().__new__(cls)
        return cls._instances["default"]

    def __init__(self):
        """Initialize factory (called only once)."""
        if not hasattr(self, "_initialized"):
            self._initialized = True
            self._classifier_type = settings.classifier_type
            self._rules_path = settings.classifier_rules_path

    async def get_classifier(self):
        """
        Get appropriate classifier instance for the configured type.

        Returns:
            An IClassifier instance (LLMClassifier, RuleBasedClassifier, or LookupTableClassifier)

        Raises:
            InvalidClassifierTypeError: If classifier_type is not supported
        """
        classifier_type = self._classifier_type

        # Check cache first
        if classifier_type in self._classifier_instances:
            return self._classifier_instances[classifier_type]

        # Instantiate based on type
        if classifier_type == "llm":
            from app.services.classifiers.llm import LLMClassifier

            instance = LLMClassifier()
        elif classifier_type == "rules":
            from app.services.classifiers.rules import RuleBasedClassifier

            instance = RuleBasedClassifier(self._rules_path)
        elif classifier_type == "lookup":
            from app.services.classifiers.lookup import LookupTableClassifier

            instance = LookupTableClassifier()
        else:
            raise InvalidClassifierTypeError(classifier_type)

        # Cache the instance
        self._classifier_instances[classifier_type] = instance
        return instance


# Singleton instance
_factory: Optional[ClassifierFactory] = None


def get_classifier_factory() -> ClassifierFactory:
    """Get the singleton ClassifierFactory instance."""
    global _factory
    if _factory is None:
        _factory = ClassifierFactory()
    return _factory
