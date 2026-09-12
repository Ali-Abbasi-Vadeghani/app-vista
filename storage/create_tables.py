from app.database import Base, engine
from app.models import AppReview, AppStats  


Base.metadata.create_all(bind=engine)

print("Storage tables created successfully.")