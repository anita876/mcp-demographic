import logging

from fastapi import APIRouter, HTTPException

from app.routes import mcp as mcp_module
from app.schemas.request_models import GetDemographicsRequest, SaveDemographicsRequest
from app.schemas.response_models import (
    DemographicsRecord,
    ListAllDemographicsResponse,
    SaveDemographicsResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tools", tags=["mcp-tools"])


@router.post(
    "/save-demographics",
    operation_id="save_demographics",
    response_model=SaveDemographicsResponse,
)
async def save_demographics_route(payload: SaveDemographicsRequest):
    """MCP tool: save a demographics record."""
    try:
        raw = mcp_module.save_demographics(
            name=payload.name,
            age_range=payload.age_range,
            region=payload.region,
            ethnicity=payload.ethnicity,
            language=payload.language,
        )
        return SaveDemographicsResponse.model_validate(raw)
    except Exception as e:
        logger.exception("save_demographics failed")
        raise HTTPException(status_code=502, detail=str(e)) from e


@router.post(
    "/get-demographics",
    operation_id="get_demographics",
    response_model=DemographicsRecord,
)
async def get_demographics_route(payload: GetDemographicsRequest):
    """MCP tool: get one demographics record by id."""
    try:
        raw = mcp_module.get_demographics(payload.record_id)
    except Exception as e:
        logger.exception("get_demographics failed")
        raise HTTPException(status_code=502, detail=str(e)) from e
    if raw.get("status") == "not_found":
        raise HTTPException(status_code=404, detail="Record not found")
    return DemographicsRecord.model_validate(raw)


@router.post(
    "/list-all-demographics",
    operation_id="list_all_demographics",
    response_model=ListAllDemographicsResponse,
)
async def list_all_demographics_route():
    """MCP tool: list all demographics records."""
    try:
        raw = mcp_module.list_all_demographics()
        return ListAllDemographicsResponse.model_validate(raw)
    except Exception as e:
        logger.exception("list_all_demographics failed")
        raise HTTPException(status_code=502, detail=str(e)) from e
