# sqlalchemy-postgres-autocommit

A library to use SQLAlchemy with PostgreSQL in an autocommit mode.

[![Build Status](https://travis-ci.org/socialwifi/sqlalchemy-postgres-autocommit.svg?branch=master)](https://travis-ci.org/socialwifi/sqlalchemy-postgres-autocommit)
[![Latest Version](https://img.shields.io/pypi/v/sqlalchemy-postgres-autocommit.svg)](https://github.com/socialwifi/sqlalchemy-postgres-autocommit/blob/master/CHANGELOG.md)
[![Supported Python versions](https://img.shields.io/pypi/pyversions/sqlalchemy-postgres-autocommit.svg)](https://pypi.python.org/pypi/sqlalchemy-postgres-autocommit/)
[![Wheel Status](https://img.shields.io/pypi/wheel/sqlalchemy-postgres-autocommit.svg)](https://pypi.python.org/pypi/sqlalchemy-postgres-autocommit/)
[![License](https://img.shields.io/pypi/l/sqlalchemy-postgres-autocommit.svg)](https://github.com/socialwifi/sqlalchemy-postgres-autocommit/blob/master/LICENSE)

## Why autocommit?

By default, SQLAlchemy opens a new transaction implicitly when you issue your first query.
Sometimes you may prefer to work with transactions explicitly and run simple statements without
transactions. This package allows to safely enable autocommit mode with PostgreSQL.

## Usage


### Configuration 
An example `myapp/db.py` file with database configuration may look like this:

```python
import sqlalchemy.ext.declarative
import sqlalchemy.orm
import sqlalchemy_postgres_autocommit


database = sqlalchemy_postgres_autocommit.AutocommitDatabase()
session = sqlalchemy.orm.scoped_session(database.session_factory)
Base = sqlalchemy.ext.declarative.declarative_base()
Base.query = session.query_property()

def setup():
    database.configure('postgresql://postgres@localhost:5432/myapp')

```

### Executing statements without transactions

When `db_session` is used, it will by default run without transactions, in an 
autocommit mode. It means that every SQL statement is executed separately and 
committed implicitly. In this context `db_session.commit()` means the same 
as `db_session.flush()` - it doesn't commit any transactions, because there 
are no transactions in progress.

An example code:
```python
from myapp import db
from myapp import models

db.db_session.add(models.User(username="frank"))
db.db_session.add(models.User(username="bob"))
db.db_session.flush()
```

roughly translates to:
```sql
INSERT INTO users (username) VALUES ('frank')
INSERT INTO users (username) VALUES ('bob')
```

with each statement committed separately, without any transactions.

### Executing statements in an explicit transaction

When an explicit transaction is needed, it may be activated like this:

```python
from myapp import db
from myapp import models

with db.session.begin():
    db.db_session.add(models.User(username="frank"))
    db.db_session.add(models.User(username="bob"))
```

Which translates roughly to:
```sql
BEGIN
INSERT INTO users (username) VALUES ('frank')
INSERT INTO users (username) VALUES ('bob')
COMMIT
```

### Using savepoints

Simply use `begin(nested=True)`:
```python
from myapp import db
from myapp import models

with db.session.begin():
    with db.session.begin(nested=True):
        db.db_session.add(models.User(username="frank"))
        db.db_session.add(models.User(username="bob"))
```

Which translates roughly to:
```sql
BEGIN
SAVEPOINT sa_savepoint_1
INSERT INTO users (username) VALUES ('frank')
INSERT INTO users (username) VALUES ('bob')
RELEASE SAVEPOINT sa_savepoint_1
COMMIT
```


## Usage in tests

A typical approach to testing with a database is to run each test case in a 
transaction and rollback that transaction when the test ends. That way SQL 
operations are executed in the database, but never committed between tests.

When the code that is being tested uses an explicit transaction, here's what happens:
* in production: first `begin()` opens a new transaction
* in test: first `begin()` starts a savepoint, because each test already runs in a transaction

### pytest fixtures

This package can be used as a pytest plugin and it provides fixtures for running tests 
in transactions.

The plugin provides the following fixtures:
* **transactional_connection** - Creates connection with an open transaction and configures the 
global session to use this connection. Any changes made to the database via
the global session will be rolled back when the test function ends. 
Uses the [Joining a Session into an External Transaction](http://docs.sqlalchemy.org/en/latest/orm/session_transaction.html#joining-a-session-into-an-external-transaction-such-as-for-test-suites) pattern from SQLAlchemy documentation.
Fixture scope: "function".
* **session** - Creates a fresh session bound to the *db_connection* declared above.
Any queries to the database in the test function, should be issued via this session - NOT via
the global session. This ensures that the test observes changes in the database, instead of
observing potentially uncommitted changes made on the global session.
Fixture scope: "function".
* **configured_connection** - a helper fixture (session-scoped) that is used by the above fixtures. 
It opens only one connection and reuses it.

For those fixtures to work, you need to configure the plugin. Configuration is done
by using fixture factories:
* `configured_connection_factory`
* `transactional_connection_factory`
* `session_factory`

Parameters:
* **autocommit_database** - the 
`sqlalchemy_postgres_autocommit.AutocommitDatabase` object used by the application. 
* **test_database_url** - a string with connection URL to the test database. 
* **sqlalchemy_session** - the global Session used by the application.
* **configured_connection_fixture_name** - name of the fixture created by `configured_connection_factory`
* **transactional_connection_fixture_name** - name of the fixture created by `transactional_connection_factory`

#### Configuration example
conftest.py:
```python
from sqlalchemy_postgres_autocommit.pytest import factories

from myapp import db


db_configured_connection = factories.configured_connection_factory(
    autocommit_database=db.database,
    test_database_url='postgresql://postgres@localhost:5432/test',
)
db_connection = factories.transactional_connection_factory(
    autocommit_database=db.database,
    sqlalchemy_session=db.session,
    configured_connection_fixture_name='db_configured_connection',
)
db_session = factories.session_factory(
    autocommit_database=db.database,
    db_connection_fixture_name='db_connection',
)
```

#### Usage example
Now, let's say we want to write two kinds of tests:
1. One that tests code that uses the database, but the test code itself doesn't 
touch the database. An example of such test is invoking a function and observing 
the results with another function.
1. Another one that makes assertions on the database - it needs a separate session for querying.

```python
@pytest.mark.usefixtures("db_connection")
def test_1():
    my_app.create_user(username="frank")
    found_users = my_app.get_users()
    assert len(found_users) == 1
    

def test_2(db_session):
    my_app.create_user(username="frank")
    found_users = db_session.query(models.User).all()
    assert len(found_users) == 1
```

### Testing and `IntegrityError`

Writing tests for code that makes a transaction dirty 
(for example by violating a constraint) may be tricky.

For example, your code might check for an `IntegrityError` and issue additional queries after that.

Example. Let's say that user's username must be unique. You might have a code like this:
```python
try:
    db.db_session.add(models.User(username="frank"))
except sqlalchemy.exc.IntegrityError:
    log_error()
...
# use the session afterwards
db.db_session.query(...)
```

In production it won't be a problem, as every statement runs separately and there's no transaction 
to make dirty.
But in tests, it's a problem, because the code will run in a transaction and will make it dirty.
Trying to execute `db.db_session.query(...)` would fail. 
That's why, during tests, `INSERT`s and `UPDATES`s are surrounded by
additional savepoints, so the outer transaction is "protected".

## Credits

http://oddbird.net/2014/06/14/sqlalchemy-postgres-autocommit/

An excellent blog post describing the problem in details. This package is based on code examples
included in this post.
