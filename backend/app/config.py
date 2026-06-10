import os
from dotenv import load_dotenv

load_dotenv()


def _required_env(name: str) -> str:
    value = os.getenv(name)
    if value:
        return value
    raise RuntimeError(f"Missing required environment variable: {name}. See .env.example.")


def _csv_env(name: str, default: str) -> list[str]:
    return [item.strip() for item in os.getenv(name, default).split(",") if item.strip()]


class Config:
    ANTHROPIC_API_KEY = _required_env("ANTHROPIC_API_KEY")
    BACKEND_CORS_ORIGINS = _csv_env("BACKEND_CORS_ORIGINS", "http://localhost:3000")
    APPROVER_DISPLAY_NAME = os.getenv("APPROVER_DISPLAY_NAME", "Demo Manager")
    # When True, writeback approve/reject endpoints return 403 (public demo safety)
    DEMO_MODE: bool = os.getenv("DEMO_MODE", "false").lower() in ("1", "true", "yes")

    ODOO_URL = os.getenv("ODOO_URL", "http://localhost:8069")
    ODOO_DB = os.getenv("ODOO_DB", "odoo_copilot")
    ODOO_USERNAME = os.getenv("ODOO_USERNAME", "admin")
    ODOO_PASSWORD = os.getenv("ODOO_PASSWORD", "admin")

    PG_DSN = (
        f"host={os.getenv('PG_HOST', 'localhost')} "
        f"port={os.getenv('PG_PORT', '5432')} "
        f"dbname={os.getenv('PG_DB', 'odoo_copilot')} "
        f"user={os.getenv('PG_USER', 'odoo')} "
        f"password={os.getenv('PG_PASSWORD', 'odoo')}"
    )

    PG_URL = (
        f"postgresql+psycopg2://{os.getenv('PG_USER', 'odoo')}:{os.getenv('PG_PASSWORD', 'odoo')}"
        f"@{os.getenv('PG_HOST', 'localhost')}:{os.getenv('PG_PORT', '5432')}"
        f"/{os.getenv('PG_DB', 'odoo_copilot')}"
    )


config = Config()
