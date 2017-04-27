from sqlalchemy_postgres_autocommit import Database


def test_sanity():
    db = Database()
    db.connect(database_url='postgresql://admin:admin@localhost:5432/test')
    assert db.engine.dialect.isolation_level == 'AUTOCOMMIT'
    s = db.Session()
    assert s.autocommit is True
