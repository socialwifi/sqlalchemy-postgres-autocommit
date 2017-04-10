from psycopg2 import extensions
from sqlalchemy import engine, event
from sqlalchemy import orm


class Database:
    def __init__(self, database_url, engine_kwargs=None):
        self.engine = engine.create_engine(database_url, isolation_level="AUTOCOMMIT", **(engine_kwargs or {}))
        self.Session = orm.sessionmaker(
            bind=self.engine,
            class_=Session,
            autocommit=True,
            autoflush=False,
        )
        # Keep track of which DBAPI connection(s) had autocommit turned off for
        # a particular transaction object.
        self.transaction_connections = {}

        event.listen(self.Session, 'after_begin', self.handle_after_transaction_begin)
        event.listen(self.Session, 'after_transaction_end', self.handle_after_transaction_end)

    def handle_after_transaction_begin(self, session, transaction, connection):
        if self.should_disable_autocommit(transaction, connection):
            self.disable_autocommit(transaction, connection)

    def should_disable_autocommit(self, transaction, connection: engine.Connection):
        dbapi_connection = self.get_dbapi_connection(connection)
        return dbapi_connection.autocommit and not transaction.nested

    def disable_autocommit(self, transaction, connection: engine.Connection):
        dbapi_connection = self.get_dbapi_connection(connection)
        dbapi_connection.autocommit = False
        self.transaction_connections.setdefault(transaction, set()).add(dbapi_connection)

    def handle_after_transaction_end(self, session, transaction):
        if self.should_reenable_autocommit(transaction):
            self.reenable_autocommit(transaction)

    def should_reenable_autocommit(self, transaction):
        return transaction in self.transaction_connections

    def reenable_autocommit(self, transaction):
        for dbapi_connection in self.transaction_connections[transaction]:
            assert not dbapi_connection.autocommit
            dbapi_connection.autocommit = True
        del self.transaction_connections[transaction]

    def get_dbapi_connection(self, connection: engine.Connection) -> extensions.connection:
        return connection.connection.connection


class Session(orm.Session):
    def commit(self):
        if self.transaction is not None or not self.autocommit:
            super().commit()
        else:
            self.flush()
