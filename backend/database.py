import os
from sqlmodel import SQLModel, create_engine, Session

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "cvtailor.db")
DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})


def init_db():
    SQLModel.metadata.create_all(engine)


def get_session():
    with Session(engine) as session:
        yield session
