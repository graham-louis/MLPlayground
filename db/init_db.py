from sqlalchemy import create_engine
from db.models import Base


import os
# Use DATABASE_URL from environment or fallback to SQLite for dev
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///mlplayground.db")
engine = create_engine(DATABASE_URL)

def init_db():
    Base.metadata.create_all(engine)

if __name__ == "__main__":
    init_db()
    print("Database tables created.")
