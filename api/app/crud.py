from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Application
from app.schemas import ApplicationCreate, ApplicationUpdate


def create_application(db: Session, data: ApplicationCreate) -> Application:
    application = Application(
        name=data.name,
        package_name=data.package_name,
        category=data.category,
    )
    db.add(application)
    db.commit()
    db.refresh(application)
    return application


def get_applications(
    db: Session, active_only: bool = False
) -> list[Application]:
    statement = select(Application).order_by(Application.id)

    if active_only:
        statement = statement.where(Application.is_active.is_(True))

    return list(db.scalars(statement).all())


def get_application(db: Session, application_id: int) -> Application | None:
    return db.get(Application, application_id)


def update_application(
    db: Session, application: Application, data: ApplicationUpdate
) -> Application:
    application.name = data.name
    application.package_name = data.package_name
    application.category = data.category
    db.commit()
    db.refresh(application)
    return application


def deactivate_application(db: Session, application: Application) -> Application:
    application.is_active = False
    db.commit()
    db.refresh(application)
    return application