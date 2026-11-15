from pathlib import Path

from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase

from config.settings import (
    _get_allowed_hosts,
    _get_database_config,
    _get_debug,
    _get_secret_key,
)


class VercelSettingsTests(SimpleTestCase):
    def test_allowed_hosts_include_vercel_deployment_and_production_domains(self):
        hosts = _get_allowed_hosts(
            {
                "DJANGO_ALLOWED_HOSTS": "localhost, example.com",
                "VERCEL_URL": "coride-git-mobile.vercel.app",
                "VERCEL_PROJECT_PRODUCTION_URL": "coride-five.vercel.app",
            }
        )

        self.assertEqual(
            hosts,
            [
                "localhost",
                "example.com",
                "coride-git-mobile.vercel.app",
                "coride-five.vercel.app",
            ],
        )

    def test_vercel_disables_debug_by_default(self):
        self.assertFalse(_get_debug({"VERCEL": "1"}))

    def test_local_debug_remains_enabled_by_default(self):
        self.assertTrue(_get_debug({}))

    def test_vercel_requires_a_secret_key(self):
        with self.assertRaises(ImproperlyConfigured):
            _get_secret_key({"VERCEL": "1"})

    def test_secret_key_uses_environment_value(self):
        self.assertEqual(
            _get_secret_key({"DJANGO_SECRET_KEY": "configured-secret"}),
            "configured-secret",
        )

    def test_local_database_defaults_to_sqlite(self):
        database = _get_database_config({}, Path("/project"))

        self.assertEqual(database["ENGINE"], "django.db.backends.sqlite3")
        self.assertEqual(database["NAME"], Path("/project/db.sqlite3"))

    def test_remote_turso_database_uses_auth_token_option(self):
        database = _get_database_config(
            {
                "TURSO_DATABASE_URL": "libsql://example.turso.io",
                "TURSO_AUTH_TOKEN": "test-token",
            },
            Path("/project"),
        )

        self.assertEqual(database["ENGINE"], "libsql.db.backends.libsql")
        self.assertEqual(database["NAME"], "libsql://example.turso.io")
        self.assertEqual(database["OPTIONS"], {"auth_token": "test-token"})

    def test_remote_turso_database_requires_auth_token(self):
        with self.assertRaises(ImproperlyConfigured):
            _get_database_config(
                {"TURSO_DATABASE_URL": "libsql://example.turso.io"},
                Path("/project"),
            )

    def test_turso_url_rejects_embedded_credentials(self):
        with self.assertRaises(ImproperlyConfigured):
            _get_database_config(
                {
                    "TURSO_DATABASE_URL": "libsql://user:secret@example.turso.io",
                    "TURSO_AUTH_TOKEN": "test-token",
                },
                Path("/project"),
            )

    def test_vercel_requires_remote_turso_credentials(self):
        with self.assertRaises(ImproperlyConfigured):
            _get_database_config({"VERCEL": "1"}, Path("/project"))
