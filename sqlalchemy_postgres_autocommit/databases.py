from psycopg2 import extensions
from sqlalchemy import engine, event
from sqlalchemy.orm import session as sqla_session


class Database:
    def __init__(self):
        self.engine = None
        self.Session = sqla_session.sessionmaker(autocommit=True, autoflush=False, class_=Session)
        # Keep track of which DBAPI connection(s) had autocommit turned off for
        # a particular transaction object.
        self.transaction_connections = {}

        event.listen(self.Session, 'after_begin', self.handle_after_transaction_begin)
        event.listen(self.Session, 'after_transaction_end', self.handle_after_transaction_end)

    def connect(self, database_url, **kwargs):
        self.engine = engine.create_engine(database_url, isolation_level="AUTOCOMMIT", **kwargs)
        self.Session.configure(bind=self.engine)

    def connect_with_connection(self, database_url, **kwargs):
        self.engine = engine.create_engine(database_url, isolation_level="AUTOCOMMIT", **kwargs)
        connection = self.engine.connect()
        self.Session.configure(bind=connection)
        return connection

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


class Session(sqla_session.Session):
    def commit(self):
        if self._in_transaction or not self.autocommit:
            super().commit()
        else:
            self.flush()

    def begin(self, *args, nested=False, **kwargs):
        if self._transaction_opened_externally():
            self.transaction = sqla_session.SessionTransaction(self)
            return super().begin(*args, nested=True, **kwargs)
        else:
            return super().begin(*args, nested=nested, **kwargs)

    def _transaction_opened_externally(self):
        return not self._in_transaction and not self._connection_autocommit_enabled

    @property
    def _in_transaction(self):
        return self.transaction is not None

    @property
    def _connection_autocommit_enabled(self):
        dbapi_connection = self.connection().connection.connection
        return dbapi_connection.autocommit
