import sqlalchemy_postgres_autocommit


def test_sanity():
    database = sqlalchemy_postgres_autocommit.AutocommitDatabase()
    database.configure(database_url='postgresql://admin:admin@localhost:5432/test')
    assert database.engine.dialect.isolation_level == 'AUTOCOMMIT'
    session = database.session_factory()
    assert session.autocommit is True
