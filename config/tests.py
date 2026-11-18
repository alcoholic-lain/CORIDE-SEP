from types import SimpleNamespace
from pathlib import Path
from unittest.mock import patch

from django.core.exceptions import ImproperlyConfigured
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase

from config.blob_storage import PrivateVercelBlobStorage
from config.settings import (
    _get_allowed_hosts,
    _get_database_config,
    _get_debug,
    _get_secret_key,
    _get_storages,
)


class VercelSettingsTests(SimpleTestCase):
    def test_allowed_hosts_include_vercel_deployment_and_production_domains(self):
        hosts = _get_allowed_hosts(
            {
                "DJANGO_ALLOWED_HOSTS": "localhost, example.com",
                "VERCEL_URL": "kizuna-git-mobile.vercel.app",
                "VERCEL_PROJECT_PRODUCTION_URL": "kizuna-five.vercel.app",
            }
        )

        self.assertEqual(
            hosts,
            [
                "localhost",
                "example.com",
                "kizuna-git-mobile.vercel.app",
                "kizuna-five.vercel.app",
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

        self.assertEqual(database["ENGINE"], "config.db_backends.turso")
        self.assertEqual(database["NAME"], "libsql://example.turso.io")
        self.assertEqual(database["OPTIONS"], {"auth_token": "test-token"})

    def test_production_uses_stable_turso_database_instead_of_deployment_branch(self):
        database = _get_database_config(
            {
                "VERCEL": "1",
                "VERCEL_ENV": "production",
                "TURSO_DATABASE_URL": "libsql://deployment-branch.turso.io",
                "TURSO_AUTH_TOKEN": "deployment-token",
                "KIZUNA_TURSO_DATABASE_URL": "libsql://stable.turso.io",
                "KIZUNA_TURSO_AUTH_TOKEN": "stable-token",
            },
            Path("/project"),
        )

        self.assertEqual(database["NAME"], "libsql://stable.turso.io")
        self.assertEqual(database["OPTIONS"], {"auth_token": "stable-token"})

    def test_non_production_vercel_keeps_its_turso_deployment_branch(self):
        database = _get_database_config(
            {
                "VERCEL": "1",
                "VERCEL_ENV": "preview",
                "TURSO_DATABASE_URL": "libsql://preview-branch.turso.io",
                "TURSO_AUTH_TOKEN": "preview-token",
                "KIZUNA_TURSO_DATABASE_URL": "libsql://stable.turso.io",
                "KIZUNA_TURSO_AUTH_TOKEN": "stable-token",
            },
            Path("/project"),
        )

        self.assertEqual(database["NAME"], "libsql://preview-branch.turso.io")
        self.assertEqual(database["OPTIONS"], {"auth_token": "preview-token"})

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

    def test_local_file_storage_remains_the_default(self):
        storages = _get_storages({})

        self.assertEqual(
            storages["default"]["BACKEND"],
            "django.core.files.storage.FileSystemStorage",
        )

    def test_blob_storage_uses_oidc_store_credentials(self):
        storages = _get_storages(
            {"BLOB_STORE_ID": "store-id", "VERCEL_OIDC_TOKEN": "short-lived-token"}
        )

        self.assertEqual(
            storages["default"]["BACKEND"],
            "config.blob_storage.PrivateVercelBlobStorage",
        )

    def test_vercel_requires_persistent_blob_credentials(self):
        with self.assertRaises(ImproperlyConfigured):
            _get_storages({"VERCEL": "1"})


class PrivateVercelBlobStorageTests(SimpleTestCase):
    @patch("config.blob_storage.blob.put_blob")
    def test_save_uploads_to_private_storage(self, put_blob):
        name = "communication/attachments/image.png"
        content = SimpleUploadedFile(
            "image.png",
            b"image bytes",
            content_type="image/png",
        )
        content.validated_content_type = "image/png"
        put_blob.return_value = SimpleNamespace(pathname=name)

        saved_name = PrivateVercelBlobStorage()._save(name, content)

        self.assertEqual(saved_name, name)
        args, kwargs = put_blob.call_args
        self.assertEqual(args[0], name)
        self.assertEqual(b"".join(args[1]), b"image bytes")
        self.assertEqual(kwargs["access"], "private")
        self.assertEqual(kwargs["content_length"], len(b"image bytes"))
        self.assertEqual(kwargs["content_type"], "image/png")

    @patch("config.blob_storage.blob.get_blob")
    def test_open_downloads_private_blob_content(self, get_blob):
        get_blob.return_value = SimpleNamespace(body=b"image bytes")

        with PrivateVercelBlobStorage()._open(
            "communication/attachments/image.png"
        ) as attachment:
            self.assertEqual(attachment.read(), b"image bytes")

        get_blob.assert_called_once_with(
            "communication/attachments/image.png",
            access="private",
        )
