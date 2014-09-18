from u2fserver.core.api import U2FServerApplication
from u2fserver.core.transactionmc import MemcachedStore
from u2fserver.core.transactiondb import DBStore
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


def create_application(settings):
    engine = create_engine(settings['db'], echo=True)

    Session = sessionmaker(bind=engine)
    session = Session()

    if settings['mc']:
        memstore = MemcachedStore(settings['mc_hosts'])
    else:
        memstore = DBStore(session)

    return U2FServerApplication(session, memstore)
