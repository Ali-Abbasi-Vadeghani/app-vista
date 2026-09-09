from app.database import SessionLocal
from app.playstore_crawler import crawl_application_stats


def main():
    db = SessionLocal()

    try:
        processed_count = crawl_application_stats(db)

        print(
            f"Successfully processed "
            f"{processed_count} applications."
        )

    finally:
        db.close()


if __name__ == "__main__":
    main()