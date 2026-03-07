"""
Excel Server Implementation for ExcelSheetsManager

A FastAPI-based server that provides HTTP endpoints for Excel file operations
using the ExcelSheetsManager class with file server backend.

Features:
- RESTful API with automatic OpenAPI documentation
- Excel file and worksheet management
- Data reading/writing with pandas DataFrame integration
- Comprehensive logging
- Health checks and metrics
- CORS support

Endpoints:
- POST /validate_sheet_name - Validate if Excel file exists
- POST /find_spreadsheet_by_name - Find Excel file by name
- POST /get_spreadsheet_folder_info - Get file and folder info
- POST /list_spreadsheets - List all Excel files
- POST /list_worksheets - Get worksheet names
- POST /validate_worksheet_name - Check if worksheet exists
- POST /create_worksheet - Create new worksheet
- POST /delete_worksheet - Delete worksheet
- POST /rename_worksheet - Rename worksheet
- POST /duplicate_worksheet - Duplicate worksheet
- POST /copy_spreadsheet_to_folder - Copy spreadsheet to folder
- POST /copy_spreadsheet_from_path - Copy spreadsheet from path
- POST /get_sheet_data - Read worksheet data as DataFrame
- POST /get_cell_value - Read single cell value
- POST /get_range_values - Read range as DataFrame
- POST /append_rows - Append DataFrame to worksheet
- POST /update_cell - Update single cell
- POST /update_range - Update range with DataFrame
- POST /insert_rows - Insert DataFrame at position
- POST /clear_range - Clear data in range
- POST /delete_rows - Delete row range
- POST /delete_columns - Delete column range
- POST /clear_worksheet - Clear all data from worksheet
- POST /clear_cache - Clear workbook cache
- GET /health - Health check endpoint
- GET /docs - Interactive API documentation
"""

import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, cast

import pandas as pd
import uvicorn
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel, Field

# Import ExcelSheetsManager and logging/context helpers
from autobots_devtools_shared_lib.converter.xlsheets import ExcelSheetsManager
from autobots_devtools_shared_lib.common.observability.logging_utils import (
    get_logger,
    set_conversation_id,
    setup_logging,
)
from autobots_devtools_shared_lib.common.utils.context_utils import (
    get_current_thread_info,
)

# Initialize logging for the application
setup_logging()

logger = get_logger(__name__)


# ============================================================================
# Configuration
# ============================================================================


class ExcelServerConfig:
    """Configuration for excel server."""

    # File server URL
    FILE_SERVER_URL = os.getenv(
        "FILE_SERVER_URL", "C:/work/src/fbp-devtools-utils/file_storage"
    )

    # Server settings
    HOST = os.getenv("EXCEL_SERVER_HOST", "0.0.0.0")
    PORT = int(os.getenv("EXCEL_SERVER_PORT", "9001"))

    # CORS settings
    ENABLE_CORS = os.getenv("ENABLE_CORS", "true").lower() == "true"
    CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*").split(",")


# ============================================================================
# Pydantic Models for Request/Response Validation
# ============================================================================


class BaseRequest(BaseModel):
    """Base request model with common parameters."""

    user_name: str = Field(..., description="User name")
    repo_name: str = Field(..., description="Repository name")
    jira_number: str = Field(..., description="JIRA number")
    agent_name: str = Field(default="paygentic", description="Agent name")


class ValidateSheetRequest(BaseRequest):
    """Request model for validating sheet name."""

    file_path: str = Field(..., description="Path to the Excel file")
    folder_path: Optional[str] = Field(None, description="Optional folder path")


class ValidateSheetResponse(BaseModel):
    """Response model for validating sheet name."""

    exists: bool


class FindSpreadsheetRequest(BaseRequest):
    """Request model for finding spreadsheet."""

    name: str = Field(..., description="Name of the Excel file")
    folder_path: Optional[str] = Field(None, description="Optional folder path")


class FindSpreadsheetResponse(BaseModel):
    """Response model for finding spreadsheet."""

    file_path: str


class SpreadsheetInfoResponse(BaseModel):
    """Response model for spreadsheet info."""

    file_path: str
    file_name: str
    folder_path: str


class ListSpreadsheetsRequest(BaseRequest):
    """Request model for listing spreadsheets."""

    folder_path: Optional[str] = Field(None, description="Optional folder path")


class ListSpreadsheetsResponse(BaseModel):
    """Response model for listing spreadsheets."""

    spreadsheets: List[Dict[str, Any]]


class ListWorksheetsRequest(BaseRequest):
    """Request model for listing worksheets."""

    file_path: str = Field(..., description="Path to the Excel file")


class ListWorksheetsResponse(BaseModel):
    """Response model for listing worksheets."""

    worksheets: List[str]


class ValidateWorksheetRequest(BaseRequest):
    """Request model for validating worksheet."""

    file_path: str = Field(..., description="Path to the Excel file")
    worksheet_name: str = Field(..., description="Name of the worksheet")


class ValidateWorksheetResponse(BaseModel):
    """Response model for validating worksheet."""

    exists: bool


class CreateWorksheetRequest(BaseRequest):
    """Request model for creating worksheet."""

    file_path: str = Field(..., description="Path to the Excel file")
    worksheet_name: str = Field(..., description="Name for the new worksheet")
    rows: Optional[int] = Field(1000, description="Number of rows")
    cols: Optional[int] = Field(26, description="Number of columns")


class WorksheetOperationResponse(BaseModel):
    """Response model for worksheet operations."""

    success: bool
    message: str


class RenameWorksheetRequest(BaseRequest):
    """Request model for renaming worksheet."""

    file_path: str = Field(..., description="Path to the Excel file")
    old_name: str = Field(..., description="Current worksheet name")
    new_name: str = Field(..., description="New worksheet name")


class DuplicateWorksheetRequest(BaseRequest):
    """Request model for duplicating worksheet."""

    file_path: str = Field(..., description="Path to the Excel file")
    source_worksheet: str = Field(..., description="Name of worksheet to duplicate")
    new_name: str = Field(..., description="Name for the duplicated worksheet")


class CopySpreadsheetRequest(BaseRequest):
    """Request model for copying spreadsheet."""

    source_file_path: str = Field(..., description="Path of the file to copy")
    destination_folder_path: str = Field(..., description="Destination folder path")
    new_name: str = Field(..., description="New name for the copied file")


class CopySpreadsheetResponse(BaseModel):
    """Response model for copying spreadsheet."""

    new_file_path: str


class GetSheetDataRequest(BaseRequest):
    """Request model for getting sheet data."""

    file_path: str = Field(..., description="Path to the Excel file")
    worksheet_name: str = Field(..., description="Name of the worksheet")
    range: Optional[str] = Field(None, description="Optional Excel range")


class GetSheetDataResponse(BaseModel):
    """Response model for getting sheet data."""

    data: List[Dict[str, Any]]  # JSON representation of DataFrame as list of records


class GetCellValueRequest(BaseRequest):
    """Request model for getting cell value."""

    file_path: str = Field(..., description="Path to the Excel file")
    worksheet_name: str = Field(..., description="Name of the worksheet")
    row: int = Field(..., description="Row number (1-indexed)")
    col: int = Field(..., description="Column number (1-indexed)")


class GetCellValueResponse(BaseModel):
    """Response model for getting cell value."""

    value: str


class GetRangeValuesRequest(BaseRequest):
    """Request model for getting range values."""

    file_path: str = Field(..., description="Path to the Excel file")
    worksheet_name: str = Field(..., description="Name of the worksheet")
    range: str = Field(..., description="Excel range")


class AppendRowsRequest(BaseRequest):
    """Request model for appending rows."""

    file_path: str = Field(..., description="Path to the Excel file")
    worksheet_name: str = Field(..., description="Name of the worksheet")
    data: Dict[str, Any] = Field(..., description="DataFrame data as dict")


class UpdateCellRequest(BaseRequest):
    """Request model for updating cell."""

    file_path: str = Field(..., description="Path to the Excel file")
    worksheet_name: str = Field(..., description="Name of the worksheet")
    row: int = Field(..., description="Row number (1-indexed)")
    col: int = Field(..., description="Column number (1-indexed)")
    value: str = Field(..., description="Value to set")


class UpdateRangeRequest(BaseRequest):
    """Request model for updating range."""

    file_path: str = Field(..., description="Path to the Excel file")
    worksheet_name: str = Field(..., description="Name of the worksheet")
    range: str = Field(..., description="Excel range")
    data: Dict[str, Any] = Field(..., description="DataFrame data as dict")


class InsertRowsRequest(BaseRequest):
    """Request model for inserting rows."""

    file_path: str = Field(..., description="Path to the Excel file")
    worksheet_name: str = Field(..., description="Name of the worksheet")
    start_row: int = Field(..., description="Row number to insert at (1-indexed)")
    data: Dict[str, Any] = Field(..., description="DataFrame data as dict")


class ClearRangeRequest(BaseRequest):
    """Request model for clearing range."""

    file_path: str = Field(..., description="Path to the Excel file")
    worksheet_name: str = Field(..., description="Name of the worksheet")
    range: str = Field(..., description="Excel range")


class DeleteRowsRequest(BaseRequest):
    """Request model for deleting rows."""

    file_path: str = Field(..., description="Path to the Excel file")
    worksheet_name: str = Field(..., description="Name of the worksheet")
    start_row: int = Field(..., description="Starting row number (1-indexed)")
    end_row: int = Field(..., description="Ending row number (1-indexed)")


class DeleteColumnsRequest(BaseRequest):
    """Request model for deleting columns."""

    file_path: str = Field(..., description="Path to the Excel file")
    worksheet_name: str = Field(..., description="Name of the worksheet")
    start_col: int = Field(..., description="Starting column number (1-indexed)")
    end_col: int = Field(..., description="Ending column number (1-indexed)")


class ClearWorksheetRequest(BaseRequest):
    """Request model for clearing worksheet."""

    file_path: str = Field(..., description="Path to the Excel file")
    worksheet_name: str = Field(..., description="Name of the worksheet")


class UpsertSheetDataRequest(BaseRequest):
    """Request model for upserting sheet data."""

    file_path: str = Field(..., description="Path to the Excel file")
    worksheet_name: str = Field(..., description="Name of the worksheet")
    data: List[Dict[str, Any]] = Field(
        ..., description="List of row objects with column name-value pairs"
    )


class HealthResponse(BaseModel):
    """Response model for health check."""

    status: str
    timestamp: str
    file_server_url: str


# ============================================================================
# FastAPI Application with Lifespan
# ============================================================================


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for startup and shutdown events.
    """
    # Startup
    logger.info("=" * 60)
    logger.info("Excel Server Starting")
    logger.info("=" * 60)
    logger.info(f"File Server URL: {ExcelServerConfig.FILE_SERVER_URL}")
    logger.info(f"CORS: {'Enabled' if ExcelServerConfig.ENABLE_CORS else 'Disabled'}")
    logger.info("=" * 60)

    # Initialize ExcelSheetsManager
    global excel_manager
    excel_manager = ExcelSheetsManager(ExcelServerConfig.FILE_SERVER_URL)

    yield

    # Shutdown
    logger.info("Excel Server Shutting Down")


app = FastAPI(
    title="Excel Server API",
    description="REST API for Excel file operations using ExcelSheetsManager",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# Configure CORS
if ExcelServerConfig.ENABLE_CORS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=ExcelServerConfig.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


# ============================================================================
# API Endpoints
# ============================================================================


@app.post(
    "/validate_sheet_name",
    response_model=ValidateSheetResponse,
    responses={
        200: {"description": "Validation result"},
    },
)
async def validate_sheet_name(request: ValidateSheetRequest):
    """
    Validate if Excel file exists and is accessible.
    """
    try:
        set_conversation_id(
            get_current_thread_info(
                user_name=request.user_name, agent_name=request.agent_name
            ).get("thread_id", "default-conversation-id")
        )

        logger.info(f"Validating sheet name: {request.file_path}")
        exists = excel_manager.validate_sheet_name(
            file_path=request.file_path,
            folder_path=request.folder_path,
            user_name=request.user_name,
            repo_name=request.repo_name,
            jira_number=request.jira_number,
        )
        return ValidateSheetResponse(exists=exists)
    except Exception as e:
        logger.error(f"Error validating sheet name: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error validating sheet name: {str(e)}",
        )


@app.post(
    "/find_spreadsheet_by_name",
    response_model=FindSpreadsheetResponse,
    responses={
        200: {"description": "Spreadsheet found"},
        404: {"description": "Spreadsheet not found"},
    },
)
async def find_spreadsheet_by_name(request: FindSpreadsheetRequest):
    """
    Find an Excel file by name and return its full path.
    """
    try:
        set_conversation_id(
            get_current_thread_info(
                user_name=request.user_name, agent_name=request.agent_name
            ).get("thread_id", "default-conversation-id")
        )

        logger.info(f"Finding spreadsheet: {request.name}")
        file_path = excel_manager.find_spreadsheet_by_name(
            name=request.name,
            folder_path=request.folder_path,
            user_name=request.user_name,
            repo_name=request.repo_name,
            jira_number=request.jira_number,
        )
        return FindSpreadsheetResponse(file_path=file_path)
    except ValueError as e:
        logger.warning(f"Spreadsheet not found: {e}")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error(f"Error finding spreadsheet: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error finding spreadsheet: {str(e)}",
        )


@app.post(
    "/get_spreadsheet_folder_info",
    response_model=SpreadsheetInfoResponse,
    responses={
        200: {"description": "Spreadsheet info"},
    },
)
async def get_spreadsheet_folder_info(request: FindSpreadsheetRequest):
    """
    Get folder information for an Excel file.
    """
    try:
        set_conversation_id(
            get_current_thread_info(
                user_name=request.user_name, agent_name=request.agent_name
            ).get("thread_id", "default-conversation-id")
        )

        logger.info(f"Getting spreadsheet info: {request.name}")
        info = excel_manager.get_spreadsheet_folder_info(
            file_path=request.name,
            user_name=request.user_name,
            repo_name=request.repo_name,
            jira_number=request.jira_number,
        )
        return SpreadsheetInfoResponse(**info)
    except Exception as e:
        logger.error(f"Error getting spreadsheet info: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting spreadsheet info: {str(e)}",
        )


@app.post(
    "/list_spreadsheets",
    response_model=ListSpreadsheetsResponse,
    responses={
        200: {"description": "List of spreadsheets"},
    },
)
async def list_spreadsheets(request: ListSpreadsheetsRequest):
    """
    List all accessible Excel files as DataFrame.
    """
    try:
        set_conversation_id(
            get_current_thread_info(
                user_name=request.user_name, agent_name=request.agent_name
            ).get("thread_id", "default-conversation-id")
        )

        logger.info(f"Listing spreadsheets in folder: {request.folder_path}")
        df = excel_manager.list_spreadsheets(
            folder_path=request.folder_path,
            user_name=request.user_name,
            repo_name=request.repo_name,
            jira_number=request.jira_number,
        )
        spreadsheets = df.to_dict("records")
        return ListSpreadsheetsResponse(spreadsheets=spreadsheets)
    except Exception as e:
        logger.error(f"Error listing spreadsheets: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error listing spreadsheets: {str(e)}",
        )


@app.post(
    "/list_worksheets",
    response_model=ListWorksheetsResponse,
    responses={
        200: {"description": "List of worksheets"},
    },
)
async def list_worksheets(request: ListWorksheetsRequest):
    """
    Get all worksheet names.
    """
    try:
        set_conversation_id(
            get_current_thread_info(
                user_name=request.user_name, agent_name=request.agent_name
            ).get("thread_id", "default-conversation-id")
        )

        worksheets = excel_manager.list_worksheets(
            file_path=request.file_path,
            user_name=request.user_name,
            repo_name=request.repo_name,
            jira_number=request.jira_number,
        )
        return ListWorksheetsResponse(worksheets=worksheets)
    except Exception as e:
        logger.error(f"Error listing worksheets: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error listing worksheets: {str(e)}",
        )


@app.post(
    "/validate_worksheet_name",
    response_model=ValidateWorksheetResponse,
    responses={
        200: {"description": "Validation result"},
    },
)
async def validate_worksheet_name(request: ValidateWorksheetRequest):
    """
    Check if worksheet exists.
    """
    try:
        set_conversation_id(
            get_current_thread_info(
                user_name=request.user_name, agent_name=request.agent_name
            ).get("thread_id", "default-conversation-id")
        )

        logger.info(
            f"Validating worksheet: {request.worksheet_name} in {request.file_path}"
        )
        exists = excel_manager.validate_worksheet_name(
            file_path=request.file_path,
            worksheet_name=request.worksheet_name,
            user_name=request.user_name,
            repo_name=request.repo_name,
            jira_number=request.jira_number,
        )
        return ValidateWorksheetResponse(exists=exists)
    except Exception as e:
        logger.error(f"Error validating worksheet: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error validating worksheet: {str(e)}",
        )


@app.post(
    "/create_worksheet",
    response_model=WorksheetOperationResponse,
    responses={
        200: {"description": "Worksheet created"},
    },
)
async def create_worksheet(request: CreateWorksheetRequest):
    """
    Create new worksheet.
    """
    try:
        set_conversation_id(
            get_current_thread_info(
                user_name=request.user_name, agent_name=request.agent_name
            ).get("thread_id", "default-conversation-id")
        )

        logger.info(
            f"Creating worksheet: {request.worksheet_name} in {request.file_path}"
        )
        success = excel_manager.create_worksheet(
            file_path=request.file_path,
            worksheet_name=request.worksheet_name,
            rows=cast(int, request.rows),
            cols=cast(int, request.cols),
            user_name=request.user_name,
            repo_name=request.repo_name,
            jira_number=request.jira_number,
        )
        message = (
            f"Worksheet '{request.worksheet_name}' created successfully"
            if success
            else f"Failed to create worksheet '{request.worksheet_name}'"
        )
        return WorksheetOperationResponse(success=success, message=message)
    except Exception as e:
        logger.error(f"Error creating worksheet: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating worksheet: {str(e)}",
        )


@app.post(
    "/delete_worksheet",
    response_model=WorksheetOperationResponse,
    responses={
        200: {"description": "Worksheet deleted"},
    },
)
async def delete_worksheet(request: ValidateWorksheetRequest):
    """
    Delete worksheet.
    """
    try:
        set_conversation_id(
            get_current_thread_info(
                user_name=request.user_name, agent_name=request.agent_name
            ).get("thread_id", "default-conversation-id")
        )

        logger.info(
            f"Deleting worksheet: {request.worksheet_name} from {request.file_path}"
        )
        success = excel_manager.delete_worksheet(
            file_path=request.file_path,
            worksheet_name=request.worksheet_name,
            user_name=request.user_name,
            repo_name=request.repo_name,
            jira_number=request.jira_number,
        )
        message = (
            f"Worksheet '{request.worksheet_name}' deleted successfully"
            if success
            else f"Failed to delete worksheet '{request.worksheet_name}'"
        )
        return WorksheetOperationResponse(success=success, message=message)
    except Exception as e:
        logger.error(f"Error deleting worksheet: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting worksheet: {str(e)}",
        )


@app.post(
    "/rename_worksheet",
    response_model=WorksheetOperationResponse,
    responses={
        200: {"description": "Worksheet renamed"},
    },
)
async def rename_worksheet(request: RenameWorksheetRequest):
    """
    Rename worksheet.
    """
    try:
        set_conversation_id(
            get_current_thread_info(
                user_name=request.user_name, agent_name=request.agent_name
            ).get("thread_id", "default-conversation-id")
        )

        logger.info(
            f"Renaming worksheet: {request.old_name} to {request.new_name} in {request.file_path}"
        )
        success = excel_manager.rename_worksheet(
            file_path=request.file_path,
            old_name=request.old_name,
            new_name=request.new_name,
            user_name=request.user_name,
            repo_name=request.repo_name,
            jira_number=request.jira_number,
        )
        message = (
            f"Worksheet renamed from '{request.old_name}' to '{request.new_name}' successfully"
            if success
            else f"Failed to rename worksheet"
        )
        return WorksheetOperationResponse(success=success, message=message)
    except Exception as e:
        logger.error(f"Error renaming worksheet: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error renaming worksheet: {str(e)}",
        )


@app.post(
    "/duplicate_worksheet",
    response_model=WorksheetOperationResponse,
    responses={
        200: {"description": "Worksheet duplicated"},
    },
)
async def duplicate_worksheet(request: DuplicateWorksheetRequest):
    """
    Duplicate worksheet.
    """
    try:
        set_conversation_id(
            get_current_thread_info(
                user_name=request.user_name, agent_name=request.agent_name
            ).get("thread_id", "default-conversation-id")
        )

        logger.info(
            f"Duplicating worksheet: {request.source_worksheet} to {request.new_name} in {request.file_path}"
        )
        success = excel_manager.duplicate_worksheet(
            file_path=request.file_path,
            source_worksheet=request.source_worksheet,
            new_name=request.new_name,
            user_name=request.user_name,
            repo_name=request.repo_name,
            jira_number=request.jira_number,
        )
        message = (
            f"Worksheet '{request.source_worksheet}' duplicated as '{request.new_name}' successfully"
            if success
            else f"Failed to duplicate worksheet"
        )
        return WorksheetOperationResponse(success=success, message=message)
    except Exception as e:
        logger.error(f"Error duplicating worksheet: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error duplicating worksheet: {str(e)}",
        )


@app.post(
    "/copy_spreadsheet_to_folder",
    response_model=CopySpreadsheetResponse,
    responses={
        200: {"description": "Spreadsheet copied"},
    },
)
async def copy_spreadsheet_to_folder(request: CopySpreadsheetRequest):
    """
    Copy an Excel file to a specific folder with a new name.
    """
    try:
        set_conversation_id(
            get_current_thread_info(
                user_name=request.user_name, agent_name=request.agent_name
            ).get("thread_id", "default-conversation-id")
        )

        logger.info(
            f"Copying spreadsheet from {request.source_file_path} to {request.destination_folder_path}/{request.new_name}"
        )
        new_path = excel_manager.copy_spreadsheet_to_folder(
            source_file_path=request.source_file_path,
            destination_folder_path=request.destination_folder_path,
            new_name=request.new_name,
            user_name=request.user_name,
            repo_name=request.repo_name,
            jira_number=request.jira_number,
        )
        return CopySpreadsheetResponse(new_file_path=new_path)
    except Exception as e:
        logger.error(f"Error copying spreadsheet: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error copying spreadsheet: {str(e)}",
        )


@app.post(
    "/copy_spreadsheet_from_path",
    response_model=CopySpreadsheetResponse,
    responses={
        200: {"description": "Spreadsheet copied"},
    },
)
async def copy_spreadsheet_from_path(request: CopySpreadsheetRequest):
    """
    Copy an Excel file from a path to a specific folder.
    """
    try:
        set_conversation_id(
            get_current_thread_info(
                user_name=request.user_name, agent_name=request.agent_name
            ).get("thread_id", "default-conversation-id")
        )

        logger.info(
            f"Copying spreadsheet from {request.source_file_path} to {request.destination_folder_path}/{request.new_name}"
        )
        new_path = excel_manager.copy_spreadsheet_from_path(
            source_path=request.source_file_path,
            destination_folder_path=request.destination_folder_path,
            new_name=request.new_name,
            user_name=request.user_name,
            repo_name=request.repo_name,
            jira_number=request.jira_number,
        )
        return CopySpreadsheetResponse(new_file_path=new_path)
    except Exception as e:
        logger.error(f"Error copying spreadsheet: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error copying spreadsheet: {str(e)}",
        )


@app.post(
    "/get_sheet_data",
    response_model=GetSheetDataResponse,
    responses={
        200: {"description": "Sheet data"},
    },
)
async def get_sheet_data(request: GetSheetDataRequest):
    """
    Read data as DataFrame.
    """
    try:
        set_conversation_id(
            get_current_thread_info(
                user_name=request.user_name, agent_name=request.agent_name
            ).get("thread_id", "default-conversation-id")
        )

        logger.info(
            f"Getting sheet data: {request.worksheet_name} from {request.file_path}"
        )
        df = excel_manager.get_sheet_data(
            file_path=request.file_path,
            worksheet_name=request.worksheet_name,
            range=request.range,
            user_name=request.user_name,
            repo_name=request.repo_name,
            jira_number=request.jira_number,
        )
        data = df.to_dict("records")
        return GetSheetDataResponse(data=data)
    except Exception as e:
        logger.error(f"Error getting sheet data: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting sheet data: {str(e)}",
        )


@app.post(
    "/get_cell_value",
    response_model=GetCellValueResponse,
    responses={
        200: {"description": "Cell value"},
    },
)
async def get_cell_value(request: GetCellValueRequest):
    """
    Read single cell.
    """
    try:
        set_conversation_id(
            get_current_thread_info(
                user_name=request.user_name, agent_name=request.agent_name
            ).get("thread_id", "default-conversation-id")
        )

        logger.info(
            f"Getting cell value at ({request.row}, {request.col}) from {request.worksheet_name} in {request.file_path}"
        )
        value = excel_manager.get_cell_value(
            file_path=request.file_path,
            worksheet_name=request.worksheet_name,
            row=request.row,
            col=request.col,
            user_name=request.user_name,
            repo_name=request.repo_name,
            jira_number=request.jira_number,
        )
        return GetCellValueResponse(value=value)
    except Exception as e:
        logger.error(f"Error getting cell value: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting cell value: {str(e)}",
        )


@app.post(
    "/get_range_values",
    response_model=GetSheetDataResponse,
    responses={
        200: {"description": "Range values"},
    },
)
async def get_range_values(request: GetRangeValuesRequest):
    """
    Read specific range as DataFrame.
    """
    try:
        set_conversation_id(
            get_current_thread_info(
                user_name=request.user_name, agent_name=request.agent_name
            ).get("thread_id", "default-conversation-id")
        )

        logger.info(
            f"Getting range values: {request.range} from {request.worksheet_name} in {request.file_path}"
        )
        df = excel_manager.get_range_values(
            file_path=request.file_path,
            worksheet_name=request.worksheet_name,
            range=request.range,
            user_name=request.user_name,
            repo_name=request.repo_name,
            jira_number=request.jira_number,
        )
        data = df.to_dict("records")
        return GetSheetDataResponse(data=data)
    except Exception as e:
        logger.error(f"Error getting range values: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting range values: {str(e)}",
        )


@app.post(
    "/append_rows",
    response_model=WorksheetOperationResponse,
    responses={
        200: {"description": "Rows appended"},
    },
)
async def append_rows(request: AppendRowsRequest):
    """
    Append DataFrame rows to end.
    """
    try:
        set_conversation_id(
            get_current_thread_info(
                user_name=request.user_name, agent_name=request.agent_name
            ).get("thread_id", "default-conversation-id")
        )

        logger.info(
            f"Appending rows to {request.worksheet_name} in {request.file_path}"
        )
        df = pd.DataFrame(request.data)
        success = excel_manager.append_rows(
            file_path=request.file_path,
            worksheet_name=request.worksheet_name,
            df=df,
            user_name=request.user_name,
            repo_name=request.repo_name,
            jira_number=request.jira_number,
        )
        message = "Rows appended successfully" if success else "Failed to append rows"
        return WorksheetOperationResponse(success=success, message=message)
    except Exception as e:
        logger.error(f"Error appending rows: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error appending rows: {str(e)}",
        )


@app.post(
    "/update_cell",
    response_model=WorksheetOperationResponse,
    responses={
        200: {"description": "Cell updated"},
    },
)
async def update_cell(request: UpdateCellRequest):
    """
    Update single cell.
    """
    try:
        set_conversation_id(
            get_current_thread_info(
                user_name=request.user_name, agent_name=request.agent_name
            ).get("thread_id", "default-conversation-id")
        )

        logger.info(
            f"Updating cell at ({request.row}, {request.col}) in {request.worksheet_name} of {request.file_path}"
        )
        success = excel_manager.update_cell(
            file_path=request.file_path,
            worksheet_name=request.worksheet_name,
            row=request.row,
            col=request.col,
            value=request.value,
            user_name=request.user_name,
            repo_name=request.repo_name,
            jira_number=request.jira_number,
        )
        message = "Cell updated successfully" if success else "Failed to update cell"
        return WorksheetOperationResponse(success=success, message=message)
    except Exception as e:
        logger.error(f"Error updating cell: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating cell: {str(e)}",
        )


@app.post(
    "/update_range",
    response_model=WorksheetOperationResponse,
    responses={
        200: {"description": "Range updated"},
    },
)
async def update_range(request: UpdateRangeRequest):
    """
    Update range with DataFrame.
    """
    try:
        set_conversation_id(
            get_current_thread_info(
                user_name=request.user_name, agent_name=request.agent_name
            ).get("thread_id", "default-conversation-id")
        )

        logger.info(
            f"Updating range {request.range} in {request.worksheet_name} of {request.file_path}"
        )
        df = pd.DataFrame(request.data)
        success = excel_manager.update_range(
            file_path=request.file_path,
            worksheet_name=request.worksheet_name,
            range=request.range,
            df=df,
            user_name=request.user_name,
            repo_name=request.repo_name,
            jira_number=request.jira_number,
        )
        message = "Range updated successfully" if success else "Failed to update range"
        return WorksheetOperationResponse(success=success, message=message)
    except Exception as e:
        logger.error(f"Error updating range: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating range: {str(e)}",
        )


@app.post(
    "/insert_rows",
    response_model=WorksheetOperationResponse,
    responses={
        200: {"description": "Rows inserted"},
    },
)
async def insert_rows(request: InsertRowsRequest):
    """
    Insert DataFrame rows at position.
    """
    try:
        set_conversation_id(
            get_current_thread_info(
                user_name=request.user_name, agent_name=request.agent_name
            ).get("thread_id", "default-conversation-id")
        )

        logger.info(
            f"Inserting rows at {request.start_row} in {request.worksheet_name} of {request.file_path}"
        )
        df = pd.DataFrame(request.data)
        success = excel_manager.insert_rows(
            file_path=request.file_path,
            worksheet_name=request.worksheet_name,
            start_row=request.start_row,
            df=df,
            user_name=request.user_name,
            repo_name=request.repo_name,
            jira_number=request.jira_number,
        )
        message = "Rows inserted successfully" if success else "Failed to insert rows"
        return WorksheetOperationResponse(success=success, message=message)
    except Exception as e:
        logger.error(f"Error inserting rows: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error inserting rows: {str(e)}",
        )


@app.post(
    "/clear_range",
    response_model=WorksheetOperationResponse,
    responses={
        200: {"description": "Range cleared"},
    },
)
async def clear_range(request: ClearRangeRequest):
    """
    Clear data in range.
    """
    try:
        set_conversation_id(
            get_current_thread_info(
                user_name=request.user_name, agent_name=request.agent_name
            ).get("thread_id", "default-conversation-id")
        )

        logger.info(
            f"Clearing range {request.range} in {request.worksheet_name} of {request.file_path}"
        )
        success = excel_manager.clear_range(
            file_path=request.file_path,
            worksheet_name=request.worksheet_name,
            range=request.range,
            user_name=request.user_name,
            repo_name=request.repo_name,
            jira_number=request.jira_number,
        )
        message = "Range cleared successfully" if success else "Failed to clear range"
        return WorksheetOperationResponse(success=success, message=message)
    except Exception as e:
        logger.error(f"Error clearing range: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error clearing range: {str(e)}",
        )


@app.post(
    "/delete_rows",
    response_model=WorksheetOperationResponse,
    responses={
        200: {"description": "Rows deleted"},
    },
)
async def delete_rows(request: DeleteRowsRequest):
    """
    Delete row range.
    """
    try:
        set_conversation_id(
            get_current_thread_info(
                user_name=request.user_name, agent_name=request.agent_name
            ).get("thread_id", "default-conversation-id")
        )

        logger.info(
            f"Deleting rows {request.start_row}-{request.end_row} in {request.worksheet_name} of {request.file_path}"
        )
        success = excel_manager.delete_rows(
            file_path=request.file_path,
            worksheet_name=request.worksheet_name,
            start_row=request.start_row,
            end_row=request.end_row,
            user_name=request.user_name,
            repo_name=request.repo_name,
            jira_number=request.jira_number,
        )
        message = "Rows deleted successfully" if success else "Failed to delete rows"
        return WorksheetOperationResponse(success=success, message=message)
    except Exception as e:
        logger.error(f"Error deleting rows: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting rows: {str(e)}",
        )


@app.post(
    "/delete_columns",
    response_model=WorksheetOperationResponse,
    responses={
        200: {"description": "Columns deleted"},
    },
)
async def delete_columns(request: DeleteColumnsRequest):
    """
    Delete column range.
    """
    try:
        set_conversation_id(
            get_current_thread_info(
                user_name=request.user_name, agent_name=request.agent_name
            ).get("thread_id", "default-conversation-id")
        )

        logger.info(
            f"Deleting columns {request.start_col}-{request.end_col} in {request.worksheet_name} of {request.file_path}"
        )
        success = excel_manager.delete_columns(
            file_path=request.file_path,
            worksheet_name=request.worksheet_name,
            start_col=request.start_col,
            end_col=request.end_col,
            user_name=request.user_name,
            repo_name=request.repo_name,
            jira_number=request.jira_number,
        )
        message = (
            "Columns deleted successfully" if success else "Failed to delete columns"
        )
        return WorksheetOperationResponse(success=success, message=message)
    except Exception as e:
        logger.error(f"Error deleting columns: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting columns: {str(e)}",
        )


@app.post(
    "/clear_worksheet",
    response_model=WorksheetOperationResponse,
    responses={
        200: {"description": "Worksheet cleared"},
    },
)
async def clear_worksheet(request: ClearWorksheetRequest):
    """
    Clear all data from a worksheet.
    """
    try:
        set_conversation_id(
            get_current_thread_info(
                user_name=request.user_name, agent_name=request.agent_name
            ).get("thread_id", "default-conversation-id")
        )

        logger.info(
            f"Clearing worksheet {request.worksheet_name} in {request.file_path}"
        )
        success = excel_manager.clear_worksheet(
            file_path=request.file_path,
            worksheet_name=request.worksheet_name,
            user_name=request.user_name,
            repo_name=request.repo_name,
            jira_number=request.jira_number,
        )
        message = (
            "Worksheet cleared successfully" if success else "Failed to clear worksheet"
        )
        return WorksheetOperationResponse(success=success, message=message)
    except Exception as e:
        logger.error(f"Error clearing worksheet: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error clearing worksheet: {str(e)}",
        )


@app.post(
    "/clear_cache",
    responses={
        200: {"description": "Cache cleared"},
    },
)
async def clear_cache():
    """
    Clear the in-memory workbook cache.
    """
    try:
        logger.info("Clearing workbook cache")
        excel_manager.clear_cache()
        return {"message": "Cache cleared successfully"}
    except Exception as e:
        logger.error(f"Error clearing cache: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error clearing cache: {str(e)}",
        )


@app.post(
    "/upsert_sheet_data",
    response_model=WorksheetOperationResponse,
    responses={
        200: {"description": "Sheet data upserted"},
    },
)
async def upsert_sheet_data(request: UpsertSheetDataRequest):
    """
    Upsert data into a worksheet. If the worksheet exists, it will be cleared first.
    If the worksheet doesn't exist, it will be created with the provided data.
    """
    try:
        set_conversation_id(
            get_current_thread_info(
                user_name=request.user_name, agent_name=request.agent_name
            ).get("thread_id", "default-conversation-id")
        )

        logger.info(
            f"Upserting data into worksheet: {request.worksheet_name} in {request.file_path}"
        )

        # Clear cache before operations to ensure fresh workbook state
        logger.info("Clearing workbook cache before upsert operation")
        excel_manager.clear_cache()

        # Convert dict to DataFrame
        df = pd.DataFrame(request.data)

        # Check if worksheet exists
        worksheet_exists = excel_manager.validate_worksheet_name(
            file_path=request.file_path,
            worksheet_name=request.worksheet_name,
            user_name=request.user_name,
            repo_name=request.repo_name,
            jira_number=request.jira_number,
        )

        if worksheet_exists:
            # Clear existing worksheet
            logger.info(
                f"Worksheet '{request.worksheet_name}' exists, clearing it first"
            )
            clear_success = excel_manager.clear_worksheet(
                file_path=request.file_path,
                worksheet_name=request.worksheet_name,
                user_name=request.user_name,
                repo_name=request.repo_name,
                jira_number=request.jira_number,
            )
            if not clear_success:
                raise Exception(f"Failed to clear worksheet '{request.worksheet_name}'")
        else:
            # Create new worksheet
            logger.info(
                f"Worksheet '{request.worksheet_name}' doesn't exist, creating it"
            )
            create_success = excel_manager.create_worksheet(
                file_path=request.file_path,
                worksheet_name=request.worksheet_name,
                rows=1000,
                cols=26,
                user_name=request.user_name,
                repo_name=request.repo_name,
                jira_number=request.jira_number,
            )
            if not create_success:
                raise Exception(
                    f"Failed to create worksheet '{request.worksheet_name}'"
                )

        # Insert data into the worksheet
        success = excel_manager.append_rows(
            file_path=request.file_path,
            worksheet_name=request.worksheet_name,
            df=df,
            user_name=request.user_name,
            repo_name=request.repo_name,
            jira_number=request.jira_number,
        )

        # Clear cache after all operations to prevent stale cache
        logger.info("Clearing workbook cache after upsert operation")
        excel_manager.clear_cache()

        if success:
            action = "cleared and updated" if worksheet_exists else "created with data"
            message = f"Worksheet '{request.worksheet_name}' {action} successfully"
        else:
            message = f"Failed to insert data into worksheet '{request.worksheet_name}'"

        return WorksheetOperationResponse(success=success, message=message)

    except Exception as e:
        logger.error(f"Error upserting sheet data: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error upserting sheet data: {str(e)}",
        )


@app.get(
    "/health",
    response_model=HealthResponse,
    responses={
        200: {"description": "Health check information"},
    },
)
async def health_check():
    """
    Health check endpoint.
    """
    try:
        return HealthResponse(
            status="healthy",
            timestamp=datetime.now(timezone.utc).isoformat(),
            file_server_url=ExcelServerConfig.FILE_SERVER_URL,
        )
    except Exception as e:
        logger.error(f"Error in health check: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Health check failed: {str(e)}",
        )


@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "name": "Excel Server API",
        "version": "1.0.0",
        "description": "REST API for Excel file operations",
        "endpoints": {
            "POST /validate_sheet_name": "Validate if Excel file exists",
            "POST /find_spreadsheet_by_name": "Find Excel file by name",
            "POST /get_spreadsheet_folder_info": "Get file and folder info",
            "POST /list_spreadsheets": "List all Excel files",
            "POST /list_worksheets": "Get worksheet names",
            "POST /validate_worksheet_name": "Check if worksheet exists",
            "POST /create_worksheet": "Create new worksheet",
            "POST /delete_worksheet": "Delete worksheet",
            "POST /rename_worksheet": "Rename worksheet",
            "POST /duplicate_worksheet": "Duplicate worksheet",
            "POST /copy_spreadsheet_to_folder": "Copy spreadsheet to folder",
            "POST /copy_spreadsheet_from_path": "Copy spreadsheet from path",
            "POST /get_sheet_data": "Read worksheet data as DataFrame",
            "POST /get_cell_value": "Read single cell value",
            "POST /get_range_values": "Read range as DataFrame",
            "POST /append_rows": "Append DataFrame to worksheet",
            "POST /update_cell": "Update single cell",
            "POST /update_range": "Update range with DataFrame",
            "POST /insert_rows": "Insert DataFrame at position",
            "POST /clear_range": "Clear data in range",
            "POST /delete_rows": "Delete row range",
            "POST /delete_columns": "Delete column range",
            "POST /clear_worksheet": "Clear all data from worksheet",
            "POST /clear_cache": "Clear workbook cache",
            "POST /upsert_sheet_data": "Upsert data into worksheet (clear existing or create new)",
            "GET /health": "Health check",
            "GET /docs": "Interactive API documentation",
        },
        "documentation": "/docs",
    }


# ============================================================================
# CLI Runner
# ============================================================================


def run_server(
    host: str | None = None,
    port: int | None = None,
    reload: bool = False,
    log_level: str = "info",
):
    """
    Run the excel server.

    Args:
        host: Host to bind to (default: from config)
        port: Port to bind to (default: from config)
        reload: Enable auto-reload for development
        log_level: Logging level
    """
    host = host or ExcelServerConfig.HOST
    port = port or ExcelServerConfig.PORT

    logger.info(f"Starting excel server on {host}:{port}")
    logger.info(f"Documentation available at http://{host}:{port}/docs")

    uvicorn.run(
        "autobots_devtools_shared_lib.common.servers.xlserver:app",
        host=host,
        port=port,
        reload=reload,
        log_level=log_level,
    )


if __name__ == "__main__":
    import sys

    # Simple CLI
    if len(sys.argv) > 1:
        if sys.argv[1] == "--help":
            print("Excel Server CLI")
            print(
                "Usage: python -m autobots_devtools_shared_lib.common.servers.xlserver [OPTIONS]"
            )
            print("\nOptions:")
            print("  --host HOST       Host to bind to (default: 0.0.0.0)")
            print("  --port PORT       Port to bind to (default: 8001)")
            print("  --reload          Enable auto-reload for development")
            print("  --help            Show this help message")
            sys.exit(0)
        elif sys.argv[1] == "--reload":
            run_server(reload=True)
        else:
            print(f"Unknown option: {sys.argv[1]}")
            print("Use --help for usage information")
            sys.exit(1)
    else:

        run_server("localhost", 9001, reload=True, log_level="debug")