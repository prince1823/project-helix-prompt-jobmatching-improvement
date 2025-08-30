"""
API endpoints for managing recruiter lists.

This module provides FastAPI routes for creating, retrieving, and querying recruiter lists.
It delegates business logic to the service layer and handles HTTP responses and errors.
"""

from sqlalchemy.orm import Session
from fastapi import status as http_status
from fastapi.responses import JSONResponse
from fastapi import APIRouter, Body, Depends, HTTPException, Path, Query

from app.db.postgres import get_db
from app.core.authorization import get_user_details

from app.repositories.recruiter_lists import Repository

from app.services.recruiter_lists import Service

from app.models.requests import ErrorResponse
from app.models.user_login import UserDetails
from app.models.recruiter_lists import Request, Response, Status, NameRequest

router = APIRouter(prefix="/recruiter-lists", tags=["Recruiter Lists"])


def get_service(db: Session = Depends(get_db)) -> Service:
    """
    Dependency to provide a Service instance with a database session.
    """
    repo = Repository(db)
    return Service(repo)


@router.post(
    "/",
    response_model=Response,
    status_code=http_status.HTTP_201_CREATED,
    responses={
        400: {"model": ErrorResponse, "description": "Bad Request"},
        409: {"model": ErrorResponse, "description": "Conflict"},
        422: {"model": ErrorResponse, "description": "Unprocessable Entity"},
    },
)
def create(
    body: Request = Body(...),
    service: Service = Depends(get_service),
    user_details: UserDetails = Depends(get_user_details),
):
    """
    Create a new recruiter list.

    Args:
        body (Request): The recruiter list creation request body.
        service (Service): The recruiter list service dependency.
        user_details (UserDetails): The authenticated user details.

    Returns:
        Response: The created recruiter list response.
    """
    try:
        return service.create(user_details, body)
    except HTTPException as http_exc:
        raise http_exc
    except Exception as exc:
        return JSONResponse(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            content={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "Request validation failed",
                    "details": [{"reason": str(exc)}],
                }
            },
        )


@router.get(
    "/",
    response_model=Response,
    status_code=http_status.HTTP_200_OK,
    responses={
        400: {"model": ErrorResponse, "description": "Bad Request"},
    },
)
def get_all(
    service: Service = Depends(get_service),
    user_details: UserDetails = Depends(get_user_details),
):
    """
    Retrieve all recruiter lists for the authenticated user.

    Args:
        service (Service): The recruiter list service dependency.
        user_details (UserDetails): The authenticated user details.

    Returns:
        Response: The recruiter lists response.
    """
    try:
        response = service.get_all(user_details)
        return response
    except HTTPException as http_exc:
        raise http_exc
    except Exception as exc:
        return JSONResponse(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            content={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "Request validation failed",
                    "details": [{"reason": str(exc)}],
                }
            },
        )


@router.get(
    "/",
    response_model=Response,
    status_code=http_status.HTTP_200_OK,
    responses={
        400: {"model": ErrorResponse, "description": "Bad Request"},
    },
)
def get_by_status(
    status: Status = Query(None),
    service: Service = Depends(get_service),
    user_details: UserDetails = Depends(get_user_details),
):
    """
    Retrieve recruiter lists filtered by status for the authenticated user.

    Args:
        status (Status): The status to filter recruiter lists by.
        service (Service): The recruiter list service dependency.
        user_details (UserDetails): The authenticated user details.

    Returns:
        Response: The recruiter lists response.
    """
    try:
        response = service.get_by_status(user_details, status)
        return response
    except HTTPException as http_exc:
        raise http_exc
    except Exception as exc:
        return JSONResponse(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            content={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "Request validation failed",
                    "details": [{"reason": str(exc)}],
                }
            },
        )


@router.get(
    "/{list_id}",
    response_model=Response,
    status_code=http_status.HTTP_200_OK,
    responses={
        400: {"model": ErrorResponse, "description": "Bad Request"},
    },
)
def get(
    list_id: int = Path(...),
    service: Service = Depends(get_service),
    user_details: UserDetails = Depends(get_user_details),
):
    """
    Retrieve a recruiter list by its ID for the authenticated user.

    Args:
        list_id (int): The recruiter list ID.
        service (Service): The recruiter list service dependency.
        user_details (UserDetails): The authenticated user details.

    Returns:
        Response: The recruiter list response.
    """
    try:
        response = service.get(user_details, list_id)
        return response
    except HTTPException as http_exc:
        raise http_exc
    except Exception as exc:
        return JSONResponse(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            content={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "Request validation failed",
                    "details": [{"reason": str(exc)}],
                }
            },
        )


@router.get(
    "/",
    response_model=Response,
    status_code=http_status.HTTP_200_OK,
    responses={
        400: {"model": ErrorResponse, "description": "Bad Request"},
    },
)
def get_by_name(
    body: NameRequest = Body(...),
    service: Service = Depends(get_service),
    user_details: UserDetails = Depends(get_user_details),
):
    """
    Retrieve recruiter lists by name for the authenticated user.

    Args:
        body (NameRequest): The request body containing the recruiter list name.
        service (Service): The recruiter list service dependency.
        user_details (UserDetails): The authenticated user details.

    Returns:
        Response: The recruiter lists response.
    """
    try:
        response = service.get_by_name(user_details, body)
        return response
    except HTTPException as http_exc:
        raise http_exc
    except Exception as exc:
        return JSONResponse(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            content={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "Request validation failed",
                    "details": [{"reason": str(exc)}],
                }
            },
        )
