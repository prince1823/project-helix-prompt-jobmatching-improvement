from typing import Optional

from sqlalchemy.orm import Session
from fastapi import status as http_status
from fastapi.responses import JSONResponse
from fastapi import APIRouter, Body, Depends, Path, Query

from app.db.postgres import get_db

from app.services.list_actions import Service
from app.core.authorization import get_user_details

from app.repositories.list_actions import Repository

from app.models.requests import ErrorResponse
from app.models.user_login import UserDetails
from app.models.list_actions import (
    Status,
    Response,
    Request,
    Actions,
    StatusResponse,
    SendResponse,
    CancelResponse,
    SendRequest,
)

router = APIRouter(prefix="/list-actions", tags=["List Actions"])


def get_service(db: Session = Depends(get_db)) -> Service:
    """
    Dependency to provide a Service instance with a database session.
    Args:
        db (Session): SQLAlchemy database session.
    Returns:
        Service: Service instance for list actions.
    """
    repo = Repository(db)
    return Service(repo)


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
    status: Optional[Status] = Query(None),
    action: Optional[Actions] = Path(...),
    service: Service = Depends(get_service),
    user_details: UserDetails = Depends(get_user_details),
):
    """
    Retrieve list actions based on list ID, status, and action type.
    Args:
        list_id (int): The unique identifier for the recruiter list.
        status (Optional[Status]): Optional status filter.
        action (Optional[Actions]): Optional action type filter.
        service (Service): Service dependency.
        user_details (UserDetails): Authenticated user details.
    Returns:
        Response: List actions response or error response.
    """
    try:
        if status is None:
            if action is None:
                return service.get_by_list(user_details, list_id)
            else:
                return service.get_by_list_type(user_details, list_id, action)
        else:
            if action is None:
                return service.get_by_list_status(user_details, list_id, status)
            else:
                return service.get_by_list_status_type(
                    user_details, list_id, status, action
                )
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


@router.post(
    "/{list_id}/add",
    response_model=StatusResponse,
    status_code=http_status.HTTP_200_OK,
    responses={
        400: {"model": ErrorResponse, "description": "Bad Request"},
    },
)
def add(
    list_id: int = Path(
        ..., description="The unique identifier for the recruiter list"
    ),
    body: Request = Body(...),
    service: Service = Depends(get_service),
    user_details: UserDetails = Depends(get_user_details),
):
    """
    Add an action to a recruiter list.
    Args:
        list_id (int): The unique identifier for the recruiter list.
        body (Request): Request body containing action details.
        service (Service): Service dependency.
        user_details (UserDetails): Authenticated user details.
    Returns:
        StatusResponse: Status of the add operation or error response.
    """
    try:
        return service.add(user_details, list_id, body)
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


@router.post(
    "/{list_id}/remove",
    response_model=StatusResponse,
    status_code=http_status.HTTP_200_OK,
    responses={
        400: {"model": ErrorResponse, "description": "Bad Request"},
    },
)
def remove(
    list_id: int = Path(
        ..., description="The unique identifier for the recruiter list"
    ),
    body: Request = Body(...),
    service: Service = Depends(get_service),
    user_details: UserDetails = Depends(get_user_details),
):
    """
    Remove an action from a recruiter list.
    Args:
        list_id (int): The unique identifier for the recruiter list.
        body (Request): Request body containing action details.
        service (Service): Service dependency.
        user_details (UserDetails): Authenticated user details.
    Returns:
        StatusResponse: Status of the remove operation or error response.
    """
    try:
        return service.remove(user_details, list_id, body)
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


@router.post(
    "/{list_id}/disable",
    response_model=StatusResponse,
    status_code=http_status.HTTP_200_OK,
    responses={
        400: {"model": ErrorResponse, "description": "Bad Request"},
    },
)
def disable(
    list_id: int = Path(
        ..., description="The unique identifier for the recruiter list"
    ),
    body: Request = Body(...),
    service: Service = Depends(get_service),
    user_details: UserDetails = Depends(get_user_details),
):
    """
    Disable an action in a recruiter list.
    Args:
        list_id (int): The unique identifier for the recruiter list.
        body (Request): Request body containing action details.
        service (Service): Service dependency.
        user_details (UserDetails): Authenticated user details.
    Returns:
        StatusResponse: Status of the disable operation or error response.
    """
    try:
        return service.disable(user_details, list_id, body)
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


@router.post(
    "/{list_id}/send",
    response_model=SendResponse,
    status_code=http_status.HTTP_200_OK,
    responses={
        400: {"model": ErrorResponse, "description": "Bad Request"},
    },
)
def send(
    list_id: int = Path(
        ..., description="The unique identifier for the recruiter list"
    ),
    body: SendRequest = Body(...),
    service: Service = Depends(get_service),
    user_details: UserDetails = Depends(get_user_details),
):
    """
    Send an action for a recruiter list.
    Args:
        list_id (int): The unique identifier for the recruiter list.
        body (SendRequest): Request body containing send action details.
        service (Service): Service dependency.
        user_details (UserDetails): Authenticated user details.
    Returns:
        SendResponse: Response of the send operation or error response.
    """
    try:
        return service.send(user_details, list_id, body)
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


@router.post(
    "/{list_id}/nudge",
    response_model=SendResponse,
    status_code=http_status.HTTP_200_OK,
    responses={
        400: {"model": ErrorResponse, "description": "Bad Request"},
    },
)
def nudge(
    list_id: int = Path(
        ..., description="The unique identifier for the recruiter list"
    ),
    body: Request = Body(...),
    service: Service = Depends(get_service),
    user_details: UserDetails = Depends(get_user_details),
):
    """
    Nudge an action in a recruiter list.
    Args:
        list_id (int): The unique identifier for the recruiter list.
        body (Request): Request body containing nudge action details.
        service (Service): Service dependency.
        user_details (UserDetails): Authenticated user details.
    Returns:
        SendResponse: Response of the nudge operation or error response.
    """
    try:
        return service.nudge(user_details, list_id, body)
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
    "/{list_id}/{action_id}/cancel",
    response_model=CancelResponse,
    status_code=http_status.HTTP_200_OK,
    responses={
        400: {"model": ErrorResponse, "description": "Bad Request"},
    },
)
def cancel(
    list_id: int = Path(
        ..., description="The unique identifier for the recruiter list"
    ),
    action_id: int = Path(..., description="The unique identifier for the action"),
    service: Service = Depends(get_service),
    user_details: UserDetails = Depends(get_user_details),
):
    """
    Cancel an action in a recruiter list.
    Args:
        list_id (int): The unique identifier for the recruiter list.
        action_id (int): The unique identifier for the action.
        service (Service): Service dependency.
        user_details (UserDetails): Authenticated user details.
    Returns:
        CancelResponse: Response of the cancel operation or error response.
    """
    try:
        return service.cancel(user_details, list_id, action_id)
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
