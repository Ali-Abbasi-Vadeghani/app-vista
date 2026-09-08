# app/main.py

from fastapi import Depends, FastAPI, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import crud
from app.database import get_db
from app.schemas import (
    ApplicationCreate,
    ApplicationResponse,
    ApplicationUpdate,
)


app = FastAPI(
    title="Sahabino API",
    description="Sahabino project API",
    version="1.0.0",
)


@app.get("/")
def root():
    return {
        "message": "Sahabino API is running"
    }


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
        new_application = crud.create_application(
            db,
            application,
        )
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Application with this package_name already exists",
        )

    if new_application is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Application with this package_name already exists",
        )

    return new_application


@app.get(
    "/applications",
    response_model=list[ApplicationResponse],
)
def get_applications(
    db: Session = Depends(get_db),
):
    return crud.get_applications(db)


@app.get(
    "/applications/{application_id}",
    response_model=ApplicationResponse,
)
def get_application(
    application_id: int,
    db: Session = Depends(get_db),
):
    application = crud.get_application(
        db,
        application_id,
    )

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
    application: ApplicationUpdate,
    db: Session = Depends(get_db),
):
    existing_application = crud.get_application(
        db,
        application_id,
    )

    if existing_application is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Application not found",
        )

    try:
        updated_application = crud.update_application(
            db,
            application_id,
            application,
        )
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Application with this package_name already exists",
        )

    if updated_application is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Application with this package_name already exists",
        )

    return updated_application


@app.delete(
    "/applications/{application_id}",
    response_model=ApplicationResponse,
)
def delete_application(
    application_id: int,
    db: Session = Depends(get_db),
):
    application = crud.deactivate_application(
        db,
        application_id,
    )

    if application is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Application not found",
        )

    return application