from app.database import Base, engine
from app.models import Application   


Base.metadata.create_all(bind=engine)
print("Tables created successfully.")