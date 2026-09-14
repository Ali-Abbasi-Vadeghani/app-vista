
from app.database import Base, engine
from app.models import NetworkMeasurement  


if __name__ == "__main__":
    Base.metadata.create_all(bind=engine)
    print("Network analyzer tables created.")