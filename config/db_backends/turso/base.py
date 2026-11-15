from collections.abc import Mapping
from itertools import tee

import turso_serverless as Database
from django.core.exceptions import ImproperlyConfigured
from django.db.backends.sqlite3.base import DatabaseWrapper as SQLiteDatabaseWrapper
from django.db.utils import NotSupportedError
from django.utils.asyncio import async_unsafe
from django.utils.regex_helper import _lazy_re_compile


FORMAT_QMARK_REGEX = _lazy_re_compile(r"(?<!%)%s")


class TursoCursorWrapper:
    def __init__(self, connection):
        self.cursor = connection.cursor()

    def __getattr__(self, name):
        return getattr(self.cursor, name)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()

    def execute(self, query, params=None):
        if params is None:
            self.cursor.execute(query)
        else:
            param_names = list(params) if isinstance(params, Mapping) else None
            query = self.convert_query(query, param_names=param_names)
            self.cursor.execute(query, params)
        return self

    def executemany(self, query, param_list):
        peekable, param_list = tee(iter(param_list))
        params = next(peekable, None)
        param_names = list(params) if isinstance(params, Mapping) else None
        query = self.convert_query(query, param_names=param_names)
        self.cursor.executemany(query, param_list)
        return self

    def convert_query(self, query, *, param_names=None):
        if param_names is None:
            return FORMAT_QMARK_REGEX.sub("?", query).replace("%%", "%")
        return query % {name: f":{name}" for name in param_names}


class DatabaseWrapper(SQLiteDatabaseWrapper):
    Database = Database

    def get_connection_params(self):
        settings_dict = self.settings_dict
        if not settings_dict["NAME"]:
            raise ImproperlyConfigured(
                "settings.DATABASES is improperly configured. "
                "Please supply the NAME value."
            )
        options = settings_dict["OPTIONS"].copy()
        self.init_commands = options.pop("init_command", "").split(";")
        self.transaction_mode = None
        return {"url": settings_dict["NAME"], **options}

    @async_unsafe
    def get_new_connection(self, conn_params):
        connection = Database.connect(**conn_params)
        connection.execute("PRAGMA foreign_keys = ON")
        for init_command in self.init_commands:
            if init_command := init_command.strip():
                connection.execute(init_command)
        return connection

    def create_cursor(self, name=None):
        if name is not None:
            raise NotSupportedError("Turso does not support named cursors.")
        return self.connection.cursor(factory=TursoCursorWrapper)

    def get_database_version(self):
        cursor = self.connection.cursor()
        try:
            version = cursor.execute("SELECT sqlite_version()").fetchone()[0]
        finally:
            cursor.close()
        return tuple(int(part) for part in version.split("."))

    def is_usable(self):
        try:
            cursor = self.connection.cursor()
            try:
                cursor.execute("SELECT 1")
            finally:
                cursor.close()
        except self.Database.Error:
            return False
        return True
