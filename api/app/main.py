import logging

from fastapi import Depends, FastAPI, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import crud
from app.database import get_db
from app.logging_config import setup_logging
from app.schemas import (
    ApplicationCreate,
    ApplicationResponse,
    ApplicationUpdate,
)


setup_logging()

logger = logging.getLogger(__name__)

app = FastAPI(
    title="AppVista API",
    description="Application list management API",
    version="1.0.0",
)


@app.get("/")
def root():
    return {"message": "AppVista API is running"}


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.post(
    "/applications",
    response_model=ApplicationResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_application(
    application: ApplicationCreate,
    db: Session = Depends(get_db),
):
    try:
        return crud.create_application(db, application)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Application with this package_name already exists",
        )


@app.get("/applications", response_model=list[ApplicationResponse])
def get_applications(
    active: bool = Query(
        False,
        description="If true, return only active applications.",
    ),
    db: Session = Depends(get_db),
):

    return crud.get_applications(db, active_only=active)


@app.get(
    "/applications/{application_id}",
    response_model=ApplicationResponse,
)
def get_application(application_id: int, db: Session = Depends(get_db)):
    application = crud.get_application(db, application_id)
    if application is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Application not found",
        )
    return application


@app.put(
    "/applications/{application_id}",
    response_model=ApplicationResponse,
)
def update_application(
    application_id: int,
    application_data: ApplicationUpdate,
    db: Session = Depends(get_db),
):
    application = crud.get_application(db, application_id)
    if application is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Application not found",
        )
    if not application.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot update an inactive application",
        )
    try:
        return crud.update_application(db, application, application_data)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Application with this package_name already exists",
        )


@app.delete(
    "/applications/{application_id}",
    response_model=ApplicationResponse,
)
def delete_application(application_id: int, db: Session = Depends(get_db)):
    application = crud.get_application(db, application_id)
    if application is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Application not found",
        )
    return crud.deactivate_application(db, application)