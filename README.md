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
from sqlalchemy_postgres_autocommit import databases


database = databases.Database()
session = sqlalchemy.orm.scoped_session(database.Session)
Base = sqlalchemy.ext.declarative.declarative_base()
Base.query = db_session.query_property()

def setup():
    database.connect('postgresql://postgres@localhost:5432/myapp')

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

An example of a pytest fixture:

```python
import pytest

@pytest.fixture
def db_connection():
    from my_app import db
    
    connection = db.database.connect_with_connection('postgresql://postgres@localhost:5432/test')
    transaction = connection.begin()
    db.database.disable_autocommit(transaction, connection)
    db.db_session.configure(bind=connection, fake_root_transaction=True)
    yield connection
    db.db_session.remove()
    transaction.rollback()
    db.database.reenable_autocommit(transaction)

```

When the code that is being tested uses an explicit transaction, here's what happens:
* in production: first `begin()` opens a new transaction
* in test: first `begin()` starts a savepoint, because each test already runs in a transaction

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
