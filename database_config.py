import os
from dotenv import load_dotenv

from sqlalchemy import create_engine, text, MetaData
from sqlalchemy.orm import declarative_base, sessionmaker

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL environment variable is not set."
    )

SCHEMA_NAME = "telso_sharthi"

engine_options = {
    "pool_pre_ping": True
}

if DATABASE_URL.startswith(("postgresql://", "postgresql+")):
    engine_options["connect_args"] = {
        "options": f"-csearch_path={SCHEMA_NAME},public"
    }

engine = create_engine(
    DATABASE_URL,
    **engine_options
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

# Create schema and ensure vector extension exists in public schema
if engine.dialect.name == "postgresql":
    with engine.begin() as connection:
        # 1. Create your custom schema
        connection.execute(
            text(f'CREATE SCHEMA IF NOT EXISTS "{SCHEMA_NAME}"')
        )

        # 2. Ensure vector extension is installed in public
        connection.execute(
            text("CREATE EXTENSION IF NOT EXISTS vector WITH SCHEMA public")
        )

        # 3. Set session search path
        connection.execute(
            text(f'SET search_path TO "{SCHEMA_NAME}", public')
        )

# Configure metadata schema
metadata = MetaData(schema=SCHEMA_NAME)

Base = declarative_base(metadata=metadata)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()