import os

PG_HOST = os.getenv("PG_HOST", "postgres")
PG_PORT = int(os.getenv("PG_PORT", "5432"))
PG_USER = os.getenv("PG_USER", "appvista")
PG_PASSWORD = os.getenv("PG_PASSWORD", "appvista123")
APP_DB = os.getenv("APP_DB", "appvista_db")
METABASE_DB = os.getenv("METABASE_DB", "metabase_db")

MB_URL = os.getenv("MB_URL", "http://metabase:3000").rstrip("/")
MB_ADMIN_EMAIL = os.getenv("MB_ADMIN_EMAIL", "admin@appvista.local")
MB_ADMIN_PASSWORD = os.getenv("MB_ADMIN_PASSWORD", "AppVista-Str0ng-2026!")
MB_ADMIN_FIRST_NAME = os.getenv("MB_ADMIN_FIRST_NAME", "AppVista")
MB_ADMIN_LAST_NAME = os.getenv("MB_ADMIN_LAST_NAME", "Admin")
MB_SITE_NAME = os.getenv("MB_SITE_NAME", "AppVista Analytics")
MB_SOURCE_NAME = os.getenv("MB_SOURCE_NAME", "AppVista PostgreSQL")
MB_DASHBOARD_NAME = os.getenv("MB_DASHBOARD_NAME", "AppVista Analytics")

SQL_FILE = os.getenv("SQL_FILE", "/app/analytics.sql")