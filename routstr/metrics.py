import asyncio
import json
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlmodel import Field, SQLModel, func, select

from .core import get_logger
from .core.db import AsyncSession, create_session
from .core.settings import settings

logger = get_logger(__name__)


class RequestMetrics(SQLModel, table=True):  # type: ignore
    __tablename__ = "request_metrics"

    id: int | None = Field(primary_key=True, default=None)
    timestamp: int = Field(index=True)
    model_id: str = Field()
    sats_spent: int = Field()
    api_key_hash: str = Field()


class DailyMetrics(SQLModel, table=True):  # type: ignore
    __tablename__ = "daily_metrics"

    date: str = Field(primary_key=True)
    total_sats: int = Field(default=0)
    total_requests: int = Field(default=0)
    per_model_spend: str = Field(default="{}")
    per_model_requests: str = Field(default="{}")
    published_to_nostr: bool = Field(default=False)
    created_at: int = Field()
    updated_at: int = Field()


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


def calculate_distribution(
    per_model_requests: dict[str, int], total: int
) -> dict[str, dict[str, Any]]:
    if total == 0:
        return {}

    distribution = {}
    for model_id, count in per_model_requests.items():
        distribution[model_id] = {
            "count": count,
            "percentage": round((count / total) * 100, 2),
        }
    return distribution


async def aggregate_daily_metrics(date_str: str) -> dict[str, Any] | None:
    date = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    start_ts = int(date.timestamp())
    end_ts = int((date + timedelta(days=1)).timestamp())

    async with create_session() as session:
        existing = await session.get(DailyMetrics, date_str)
        if existing:
            return {
                "date": date_str,
                "total_sats": existing.total_sats,
                "total_requests": existing.total_requests,
                "per_model_spend": json.loads(existing.per_model_spend),
                "per_model_requests": json.loads(existing.per_model_requests),
                "already_aggregated": True,
            }

        stmt = (
            select(
                RequestMetrics.model_id,
                func.sum(RequestMetrics.sats_spent).label("total_sats"),
                func.count().label("request_count"),
            )
            .where(
                RequestMetrics.timestamp >= start_ts, RequestMetrics.timestamp < end_ts
            )
            .group_by(RequestMetrics.model_id)
        )

        result = await session.exec(stmt)
        rows = result.all()

        total_sats = 0
        total_requests = 0
        per_model_spend: dict[str, int] = {}
        per_model_requests: dict[str, int] = {}

        for row in rows:
            model_id, model_sats, model_count = row
            total_sats += model_sats or 0
            total_requests += model_count or 0
            per_model_spend[model_id] = model_sats or 0
            per_model_requests[model_id] = model_count or 0

        min_threshold = getattr(settings, "metrics_min_threshold", 10)
        if total_requests < min_threshold:
            return None

        daily_metric = DailyMetrics(
            date=date_str,
            total_sats=total_sats,
            total_requests=total_requests,
            per_model_spend=json.dumps(per_model_spend),
            per_model_requests=json.dumps(per_model_requests),
            published_to_nostr=False,
            created_at=int(datetime.now(timezone.utc).timestamp()),
            updated_at=int(datetime.now(timezone.utc).timestamp()),
        )
        session.add(daily_metric)
        await session.commit()

        return {
            "date": date_str,
            "total_sats": total_sats,
            "total_requests": total_requests,
            "per_model_spend": per_model_spend,
            "per_model_requests": per_model_requests,
            "per_model_distribution": calculate_distribution(
                per_model_requests, total_requests
            ),
        }


async def daily_metrics_aggregator() -> None:
    if not getattr(settings, "metrics_enabled", True):
        logger.info("Metrics aggregation disabled")
        return

    while True:
        try:
            publish_hour = getattr(settings, "metrics_publish_hour", 1)
            now = datetime.now(timezone.utc)

            next_publish = now.replace(
                hour=publish_hour, minute=0, second=0, microsecond=0
            )
            if now >= next_publish:
                next_publish += timedelta(days=1)

            wait_seconds = (next_publish - now).total_seconds()
            logger.info(
                f"Next metrics aggregation scheduled for {next_publish.isoformat()}"
            )
            await asyncio.sleep(wait_seconds)

            yesterday = (now - timedelta(days=1)).strftime("%Y-%m-%d")
            metrics = await aggregate_daily_metrics(yesterday)

            if metrics and not metrics.get("already_aggregated"):
                logger.info(
                    f"Aggregated metrics for {yesterday}: "
                    f"{metrics['total_requests']} requests, "
                    f"{metrics['total_sats']} sats"
                )

        except asyncio.CancelledError:
            logger.info("Metrics aggregator stopped")
            break
        except Exception as e:
            logger.error(f"Metrics aggregator error: {e}")
            await asyncio.sleep(3600)
