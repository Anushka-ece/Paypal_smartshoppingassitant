from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker
from app.config import DATABASE_URL

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_timescaledb(db_engine=None):
    """Initializes TimescaleDB extension and hypertable for ledger_entries partitioned on created_at."""
    target_engine = db_engine or engine
    try:
        with target_engine.connect() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;"))
            conn.execute(
                text("SELECT create_hypertable('ledger_entries', 'created_at', if_not_exists => TRUE);")
            )
            conn.commit()
    except Exception as e:
        # Gracefully catch when timescaledb extension is unavailable (e.g. SQLite or plain Postgres)
        pass
