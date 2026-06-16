import os
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

project_root = Path(__file__).resolve().parents[3]
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{project_root / 'complisoc.db'}")

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

#session.py is responsible for the database connection. It reads the database URL from the environment if available, otherwise falls back to a default path pointing at complisoc.db. 
#SQLAlchemy engine — the object that knows how to talk to SQLite
#the SessionLocal factory is a class that produces individual database sessions on demand. 
#get_db() - a generator function that yields a session and closes it automatically when the caller is done. 
# This pattern is what FastAPI uses for dependency injection later — a route handler declares it needs a database session and FastAPI calls get_db() to provide one

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
