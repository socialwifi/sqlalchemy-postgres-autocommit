import pytest


@pytest.fixture(scope="session")
def configured_autocommit_connection(autocommit_database, test_database_url):
    autocommit_database.configure_engine(test_database_url)
    return autocommit_database.create_connection_with_bound_session()


@pytest.fixture
def db_connection(configured_autocommit_connection, autocommit_database, sqlalchemy_session):
    connection = configured_autocommit_connection
    transaction = connection.begin()
    autocommit_database.disable_autocommit(transaction, connection)
    sqlalchemy_session.configure(bind=connection, fake_root_transaction=True)
    yield connection
    sqlalchemy_session.remove()
    transaction.rollback()
    autocommit_database.reenable_autocommit(transaction)


@pytest.fixture
def db_session(autocommit_database, db_connection):
    session = autocommit_database.session_factory(bind=db_connection)
    yield session
    session.close()
