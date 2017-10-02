import pytest


def configured_connection_factory(autocommit_database, test_database_url):
    @pytest.fixture(scope="session")
    def configured_connection_fixture():
        autocommit_database.configure_engine(test_database_url)
        return autocommit_database.create_connection_with_bound_session()

    return configured_connection_fixture


def transactional_connection_factory(autocommit_database, sqlalchemy_session, configured_connection_fixture_name):
    @pytest.fixture
    def transactional_connection_fixture(request):
        connection = request.getfixturevalue(configured_connection_fixture_name)
        transaction = connection.begin()
        autocommit_database.disable_autocommit(transaction, connection)
        sqlalchemy_session.configure(bind=connection, fake_root_transaction=True)
        yield connection
        sqlalchemy_session.remove()
        transaction.rollback()
        autocommit_database.reenable_autocommit(transaction)

    return transactional_connection_fixture


def session_factory(autocommit_database, transactional_connection_fixture_name):
    @pytest.fixture
    def session_fixture(request):
        transactional_connection = request.getfixturevalue(transactional_connection_fixture_name)
        session = autocommit_database.session_factory(bind=transactional_connection)
        yield session
        session.close()

    return session_fixture
