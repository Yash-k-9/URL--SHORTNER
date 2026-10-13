from sqlalchemy import create_engine

from sqlalchemy.orm import declarative_base, sessionmaker

db_url='postgresql+psycopg2://postgres:......@localhost:5432/sqlproj'
engine = create_engine(db_url)

SessionLocal=sessionmaker(autocommit=False,bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
