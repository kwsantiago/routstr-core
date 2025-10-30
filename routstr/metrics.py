from datetime import datetime, timezone

from sqlmodel import Field, SQLModel

from .core import get_logger
from .core.db import AsyncSession

logger = get_logger(__name__)


class RequestMetrics(SQLModel, table=True):  # type: ignore
    __tablename__ = "request_metrics"

    id: int | None = Field(primary_key=True, default=None)
    timestamp: int = Field(index=True)
    model_id: str = Field()
    sats_spent: int = Field()
    api_key_hash: str = Field()


async def track_request_metric(
    session: AsyncSession, model_id: str, sats_spent: int, api_key_hash: str
) -> None:
    try:
        metric = RequestMetrics(
            timestamp=int(datetime.now(timezone.utc).timestamp()),
            model_id=model_id,
            sats_spent=sats_spent,
            api_key_hash=api_key_hash,
        )
        session.add(metric)
        await session.commit()
    except Exception as e:
        logger.error(f"Failed to track metric: {e}")
