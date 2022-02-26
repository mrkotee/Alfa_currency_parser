
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session


def create_session(sqlite_base_path, scoped=False):
    engine = create_engine('sqlite:///%s' % sqlite_base_path, echo=False)
    if scoped:
        return scoped_session(sessionmaker(bind=engine))
    return sessionmaker(bind=engine)()
