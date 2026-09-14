
from app.database import Base, engine
from app.models import AppReview, AppStats, NetworkMeasurement  


Base.metadata.create_all(bind=engine)

print("Storage tables created successfully.")