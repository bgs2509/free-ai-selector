"""
Analytics & Journal proxy routes for AI Manager Platform - Business API Service

The Data API is not reachable from the browser, so these endpoints proxy
per-project ("caller") analytics and the request journal (inspector) through
the existing DataAPIClient over HTTP. Access is gated by the external nginx
proxy; no auth is implemented here.
"""

from typing import List, Optional

from fastapi import APIRouter, HTTPException, Request, status

from app.infrastructure.http_clients.data_api_client import DataAPIClient
from app.utils.logger import get_logger
from app.utils.security import sanitize_error_message

logger = get_logger(__name__)

router = APIRouter(tags=["Analytics"])


@router.get("/analytics/by-project", summary="Per-project (caller) usage analytics")
async def get_analytics_by_project(request: Request, window_days: int = 7) -> List[dict]:
    """Per-project aggregates: request count, success rate, avg latency, top model."""
    request_id = getattr(request.state, "request_id", None)
    data_api_client = DataAPIClient(request_id=request_id)
    try:
        return await data_api_client.get_caller_statistics(window_days=window_days)
    except Exception as e:
        logger.error("analytics_by_project_failed", error=sanitize_error_message(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch analytics: {sanitize_error_message(e)}",
        )
    finally:
        await data_api_client.close()


@router.get("/history", summary="Request journal (filtered list)")
async def get_history(
    request: Request,
    caller: Optional[str] = None,
    success: Optional[bool] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
) -> List[dict]:
    """Journal list with optional filters by caller / success / date range."""
    request_id = getattr(request.state, "request_id", None)
    data_api_client = DataAPIClient(request_id=request_id)
    try:
        return await data_api_client.get_history(
            caller=caller,
            success=success,
            date_from=date_from,
            date_to=date_to,
            limit=limit,
            offset=offset,
        )
    except Exception as e:
        logger.error("get_history_failed", error=sanitize_error_message(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch history: {sanitize_error_message(e)}",
        )
    finally:
        await data_api_client.close()


@router.get("/history/{history_id}", summary="Request journal entry detail")
async def get_history_detail(history_id: int, request: Request) -> dict:
    """Full drill-down for a single request: prompt, params, response, status."""
    request_id = getattr(request.state, "request_id", None)
    data_api_client = DataAPIClient(request_id=request_id)
    try:
        record = await data_api_client.get_history_by_id(history_id)
        if record is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"History record {history_id} not found",
            )
        return record
    except HTTPException:
        raise
    except Exception as e:
        logger.error("get_history_detail_failed", error=sanitize_error_message(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch history record: {sanitize_error_message(e)}",
        )
    finally:
        await data_api_client.close()
