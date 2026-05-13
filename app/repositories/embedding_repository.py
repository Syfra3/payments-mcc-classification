"""Embedding repository for similarity search."""

from typing import List, Optional, Tuple
from uuid import UUID
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.embedding import Embedding
from app.core.context import get_session


class EmbeddingRepository:
    """Repository for Embedding entity."""

    def __init__(self, session: Optional[AsyncSession] = None):
        """Initialize with optional session."""
        self.session = session

    def _get_session(self) -> AsyncSession:
        """Get the current session from context or parameter."""
        session = self.session or get_session()
        if not session:
            raise RuntimeError("No database session available")
        return session

    async def create(self, embedding: Embedding) -> Embedding:
        """Create and persist an embedding."""
        session = self._get_session()
        session.add(embedding)
        await session.flush()
        return embedding

    async def get_by_resource(
        self, resource_type: str, resource_id: UUID
    ) -> Optional[Embedding]:
        """Get embedding by resource type and ID."""
        session = self._get_session()
        stmt = select(Embedding).where(
            and_(
                Embedding.resource_type == resource_type,
                Embedding.resource_id == resource_id,
            )
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def search_similar(
        self,
        query_embedding: List[float],
        resource_type: str,
        threshold: float = 0.0,
        limit: int = 10,
    ) -> List[Tuple[Embedding, float]]:
        """Search for similar embeddings by cosine distance."""
        session = self._get_session()

        stmt = (
            select(
                Embedding,
                (1 - (Embedding.embedding.op("<->")(query_embedding))).label("similarity"),
            )
            .where(
                and_(
                    Embedding.resource_type == resource_type,
                    Embedding.embedding.isnot(None),
                    (1 - (Embedding.embedding.op("<->")(query_embedding))) >= threshold,
                )
            )
            .order_by((1 - (Embedding.embedding.op("<->")(query_embedding))).desc())
            .limit(limit)
        )

        result = await session.execute(stmt)
        return [(row[0], float(row[1])) for row in result.all()]

    async def upsert(
        self, resource_type: str, resource_id: UUID, embedding: List[float]
    ) -> Embedding:
        """Create or update an embedding."""
        session = self._get_session()

        existing = await self.get_by_resource(resource_type, resource_id)
        if existing:
            existing.embedding = embedding
            await session.flush()
            return existing

        new_embedding = Embedding(
            resource_type=resource_type,
            resource_id=resource_id,
            embedding=embedding,
        )
        session.add(new_embedding)
        await session.flush()
        return new_embedding

    async def delete(self, resource_type: str, resource_id: UUID) -> bool:
        """Delete an embedding."""
        session = self._get_session()
        embedding = await self.get_by_resource(resource_type, resource_id)
        if not embedding:
            return False

        await session.delete(embedding)
        await session.flush()
        return True
