"""Embedding storage and similarity search provider."""

import math
from typing import Optional, Tuple, List
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text, func, Float
from sqlalchemy.orm import selectinload

from app.models import Embedding
import structlog

logger = structlog.get_logger(__name__)


def cosine_similarity(v1: list[float], v2: list[float]) -> float:
    """
    Compute cosine similarity between two vectors.

    Args:
        v1: First vector
        v2: Second vector

    Returns:
        Similarity score between -1 and 1
    """
    if not v1 or not v2:
        return 0.0

    if len(v1) != len(v2):
        raise ValueError(f"Vector dimensions must match: {len(v1)} vs {len(v2)}")

    # Compute dot product
    dot_product = sum(a * b for a, b in zip(v1, v2))

    # Compute norms
    norm_v1 = math.sqrt(sum(a * a for a in v1))
    norm_v2 = math.sqrt(sum(b * b for b in v2))

    # Avoid division by zero
    if norm_v1 == 0 or norm_v2 == 0:
        return 0.0

    return dot_product / (norm_v1 * norm_v2)


async def store_embedding(
    resource_type: str,
    resource_id: UUID,
    embedding: list[float],
    session: AsyncSession,
) -> Embedding:
    """
    Store or update an embedding in the database.

    Args:
        resource_type: Type of resource (e.g., "merchant", "mcc")
        resource_id: ID of the resource
        embedding: Embedding vector
        session: Database session

    Returns:
        Stored Embedding entity
    """
    # Try to find existing embedding
    from sqlalchemy import select

    stmt = select(Embedding).where(
        (Embedding.resource_type == resource_type) & (Embedding.resource_id == resource_id)
    )
    result = await session.execute(stmt)
    existing = result.scalar_one_or_none()

    if existing:
        # Update existing
        existing.embedding = embedding
        logger.debug(f"Updated embedding for {resource_type}:{resource_id}")
    else:
        # Create new
        existing = Embedding(
            resource_type=resource_type,
            resource_id=resource_id,
            embedding=embedding,
        )
        session.add(existing)
        logger.debug(f"Created embedding for {resource_type}:{resource_id}")

    await session.flush()
    return existing


async def search_embeddings_by_similarity(
    query_embedding: list[float],
    resource_type: str,
    threshold: float = 0.7,
    limit: int = 10,
    session: Optional[AsyncSession] = None,
) -> List[Tuple[Embedding, float]]:
    """
    Search for embeddings by cosine similarity using pgvector.

    Args:
        query_embedding: Query embedding vector
        resource_type: Type of resource to search
        threshold: Minimum similarity threshold (0-1)
        limit: Maximum number of results
        session: Database session

    Returns:
        List of (Embedding, similarity_score) tuples, sorted by similarity descending
    """
    if not session:
        from app.core.context import get_session

        session = get_session()
        if not session:
            logger.error("No database session available for embedding search")
            return []

    try:
        # Use pgvector <-> operator for cosine distance
        # Note: pgvector's <-> operator returns distance, not similarity
        # Distance = 1 - cosine_similarity, so we need to invert it

        stmt = text(
            """
            SELECT id, resource_type, resource_id, embedding,
                   1 - (embedding <-> :query_embedding) as similarity
            FROM embedding
            WHERE resource_type = :resource_type
              AND 1 - (embedding <-> :query_embedding) >= :threshold
            ORDER BY similarity DESC
            LIMIT :limit
            """
        )

        result = await session.execute(
            stmt,
            {
                "query_embedding": query_embedding,
                "resource_type": resource_type,
                "threshold": threshold,
                "limit": limit,
            },
        )

        rows = result.fetchall()

        if not rows:
            logger.debug(
                f"No embeddings found for {resource_type} with threshold {threshold}"
            )
            return []

        # Convert rows to (Embedding, similarity) tuples
        embeddings_with_scores: List[Tuple[Embedding, float]] = []

        for row in rows:
            # Reconstruct Embedding object from row
            embedding_obj = Embedding(
                id=row[0],
                resource_type=row[1],
                resource_id=row[2],
                embedding=row[3],
            )
            similarity = row[4]
            embeddings_with_scores.append((embedding_obj, similarity))

        logger.info(f"Found {len(embeddings_with_scores)} embeddings for {resource_type}")
        return embeddings_with_scores

    except Exception as e:
        logger.error(f"Error searching embeddings: {e}", error=str(e))
        raise
