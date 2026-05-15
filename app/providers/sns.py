"""AWS SNS provider for event publishing (optional in v1)."""

from typing import Dict, Any
import json
import structlog

logger = structlog.get_logger(__name__)


class SnsPublisher:
    """AWS SNS client for publishing events."""

    def __init__(self, topic_arn: str, region: str = "us-east-1"):
        """Initialize SNS publisher."""
        if not topic_arn:
            raise ValueError("SNS topic ARN is required")

        self.topic_arn = topic_arn
        self._region = region
        self._sns_client = None

    def _get_client(self):
        """Lazily initialize boto3 SNS client."""
        if self._sns_client is not None:
            return self._sns_client

        try:
            import boto3

            self._sns_client = boto3.client("sns", region_name=self._region)
            logger.info(f"SNS client initialized for topic: {self.topic_arn}")
            return self._sns_client

        except ImportError:
            logger.error("boto3 package not installed, SNS operations will fail")
            raise
        except Exception as e:
            logger.error(f"Failed to initialize SNS client: {e}")
            raise

    @property
    def provider_name(self) -> str:
        """Get the provider name."""
        return "sns"

    async def publish(self, message: Dict[str, Any], event_type: str) -> str:
        """
        Publish a message to SNS topic.

        Args:
            message: Message payload as dict
            event_type: Type of event (e.g., "merchant_created")

        Returns:
            MessageId from SNS
        """
        try:
            client = self._get_client()
            response = client.publish(
                TopicArn=self.topic_arn,
                Message=json.dumps(message),
                Subject=event_type,
                MessageAttributes={
                    "event_type": {
                        "DataType": "String",
                        "StringValue": event_type
                    }
                }
            )
            logger.info(
                "Message published to SNS",
                message_id=response.get("MessageId"),
                event_type=event_type,
                topic_arn=self.topic_arn
            )
            return response.get("MessageId")
        except Exception as e:
            logger.error(
                "Failed to publish message to SNS",
                error=str(e),
                event_type=event_type
            )
            raise
