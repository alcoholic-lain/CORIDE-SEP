from django.test import SimpleTestCase

from config.settings import _get_allowed_hosts, _get_debug


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
