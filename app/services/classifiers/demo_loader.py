"""Demo topics loader for bootstrap initialization."""

import os
import yaml
import structlog
from typing import Optional
from app.models.mcc import Category
from app.repositories.mcc_repository import CategoryRepository
from app.core.config import settings

logger = structlog.get_logger(__name__)


async def load_demo_topics(config_path: str = "config/demo_topics.yaml") -> None:
    """Load demo topics on application startup.

    Idempotent: skips categories that already exist for the tenant.
    Only runs if DEMO_TOPICS=True in configuration.

    Args:
        config_path: Path to demo_topics.yaml configuration file
    """
    if not settings.demo_topics:
        logger.info("Demo topics loading disabled (DEMO_TOPICS=False)")
        return

    if not os.path.exists(config_path):
        logger.warning(
            "Demo topics configuration file not found",
            config_path=config_path,
        )
        return

    try:
        # Load YAML configuration
        with open(config_path, "r") as f:
            config = yaml.safe_load(f)

        if not config:
            logger.warning("Demo topics configuration is empty")
            return

        # Get default tenant categories
        tenant_config = config.get(settings.default_tenant, {})
        categories_def = tenant_config.get("categories", [])

        if not categories_def:
            logger.warning(
                "No categories defined for default tenant in demo config",
                default_tenant=settings.default_tenant,
            )
            return

        # Create categories in database
        category_repo = CategoryRepository()
        created_count = 0

        for cat_def in categories_def:
            cat_name = cat_def.get("name")
            cat_desc = cat_def.get("description")

            if not cat_name:
                logger.warning("Category missing name field", category_def=cat_def)
                continue

            # Check if category already exists
            existing = await category_repo.get_by_name(
                cat_name, settings.default_tenant
            )
            if existing:
                logger.info(
                    "Category already exists, skipping",
                    category_name=cat_name,
                    tenant_id=settings.default_tenant,
                )
                continue

            # Create new category
            category = Category(
                name=cat_name,
                description=cat_desc,
                tenant_id=settings.default_tenant,
            )

            await category_repo.create(category)
            created_count += 1
            logger.info(
                "Created demo category",
                category_name=cat_name,
                tenant_id=settings.default_tenant,
            )

        logger.info(
            "Demo topics loaded",
            created_count=created_count,
            total_count=len(categories_def),
            default_tenant=settings.default_tenant,
        )

    except yaml.YAMLError as e:
        logger.error(
            "Invalid YAML in demo topics configuration",
            config_path=config_path,
            error=str(e),
        )
    except Exception as e:
        logger.error(
            "Failed to load demo topics",
            config_path=config_path,
            error=str(e),
        )
