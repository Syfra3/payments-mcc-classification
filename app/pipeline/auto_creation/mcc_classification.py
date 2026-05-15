"""MCC classification step (deprecated, use topic_classification instead).

This module is maintained for backward compatibility.
New code should use TopicClassificationStep from topic_classification module.
"""

from app.pipeline.auto_creation.topic_classification import TopicClassificationStep

# Backward compatibility alias
MccClassificationStep = TopicClassificationStep

__all__ = ["MccClassificationStep"]
