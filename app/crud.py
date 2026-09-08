# app/crud.py

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Application
from app.schemas import ApplicationCreate, ApplicationUpdate


def create_application(
    db: Session,
    application: ApplicationCreate,
) -> Application | None:

    existing_application = db.scalar(
        select(Application).where(
            Application.package_name == application.package_name
        )
    )

    if existing_application:
        return None

    new_application = Application(
        name=application.name,
        package_name=application.package_name,
        category=application.category,
        is_active=True,
    )

    db.add(new_application)
    db.commit()
    db.refresh(new_application)

    return new_application


def get_applications(
    db: Session,
) -> list[Application]:

    statement = select(Application).order_by(Application.id)

    return list(db.scalars(statement).all())


def get_application(
    db: Session,
    application_id: int,
) -> Application | None:

    return db.get(Application, application_id)


def update_application(
    db: Session,
    application_id: int,
    application: ApplicationUpdate,
) -> Application | None:

    existing_application = db.get(
        Application,
        application_id,
    )

    if existing_application is None:
        return None

    duplicate_application = db.scalar(
        select(Application).where(
            Application.package_name == application.package_name,
            Application.id != application_id,
        )
    )

    if duplicate_application:
        return None

    existing_application.name = application.name
    existing_application.package_name = application.package_name
    existing_application.category = application.category

    db.commit()
    db.refresh(existing_application)

    return existing_application


def deactivate_application(
    db: Session,
    application_id: int,
) -> Application | None:

    existing_application = db.get(
        Application,
        application_id,
    )

    if existing_application is None:
        return None

    existing_application.is_active = False

    db.commit()
    db.refresh(existing_application)

    return existing_application