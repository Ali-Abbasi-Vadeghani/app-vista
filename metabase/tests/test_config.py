
from app import config


def test_config_defaults():
    assert config.PG_HOST == "postgres"
    assert config.PG_PORT == 5432
    assert config.APP_DB == "appvista_db"
    assert config.METABASE_DB == "metabase_db"


def test_config_metabase_defaults():
    assert config.MB_URL == "http://metabase:3000"
    assert config.MB_SOURCE_NAME == "AppVista PostgreSQL"
    assert config.MB_DASHBOARD_NAME == "AppVista Analytics"


