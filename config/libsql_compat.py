def prepare_libsql_driver():
    import sqlite3.dbapi2

    if not hasattr(sqlite3.dbapi2, "version"):
        # libsql-client still imports this deprecated field, removed in Python 3.14.
        setattr(sqlite3.dbapi2, "version", "2.6.0")
