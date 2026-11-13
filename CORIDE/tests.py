from unittest.mock import patch

from django.core.management import CommandError, call_command
from django.test import SimpleTestCase, override_settings

from CORIDE.management.commands.corideserver import get_lan_address


class LANAddressTests(SimpleTestCase):
    @patch("CORIDE.management.commands.corideserver.socket.socket")
    def test_uses_the_selected_private_network_address(self, mock_socket):
        probe = mock_socket.return_value.__enter__.return_value
        probe.getsockname.return_value = ("192.168.100.68", 12345)

        self.assertEqual(get_lan_address(), "192.168.100.68")
        probe.connect.assert_called_once_with(("192.0.2.1", 9))

    @patch("CORIDE.management.commands.corideserver.socket.socket")
    def test_rejects_non_private_addresses(self, mock_socket):
        probe = mock_socket.return_value.__enter__.return_value
        probe.getsockname.return_value = ("8.8.8.8", 12345)

        with self.assertRaises(CommandError):
            get_lan_address()


class CoRideServerCommandTests(SimpleTestCase):
    @override_settings(DEBUG=True)
    @patch.dict("os.environ", {"RUN_MAIN": "true"})
    @patch("CORIDE.management.commands.corideserver.call_command")
    @patch(
        "CORIDE.management.commands.corideserver.get_lan_address",
        return_value="192.168.100.68",
    )
    @patch("CORIDE.management.commands.corideserver.Zeroconf")
    def test_advertises_the_server_and_runs_django(
        self,
        mock_zeroconf_class,
        _mock_get_lan_address,
        mock_call_command,
    ):
        zeroconf = mock_zeroconf_class.return_value.__enter__.return_value

        call_command("corideserver", port=8001)

        service = zeroconf.register_service.call_args.args[0]
        self.assertEqual(service.type, "_coride._tcp.local.")
        self.assertEqual(service.port, 8001)
        self.assertEqual(service.parsed_addresses(), ["192.168.100.68"])
        _mock_get_lan_address.assert_called_once_with()
        mock_call_command.assert_called_once_with(
            "runserver",
            "0.0.0.0:8001",
            use_reloader=False,
        )
        zeroconf.unregister_service.assert_called_once_with(service)

    @override_settings(DEBUG=True)
    @patch.dict("os.environ", {"RUN_MAIN": ""})
    @patch("CORIDE.management.commands.corideserver.call_command")
    @patch("CORIDE.management.commands.corideserver.Zeroconf")
    def test_autoreloader_parent_does_not_register_a_second_service(
        self,
        mock_zeroconf_class,
        mock_call_command,
    ):
        call_command("corideserver", port=8001)

        mock_zeroconf_class.assert_not_called()
        mock_call_command.assert_called_once_with(
            "runserver",
            "0.0.0.0:8001",
            use_reloader=True,
        )

    @override_settings(DEBUG=False)
    def test_command_is_restricted_to_debug_mode(self):
        with self.assertRaises(CommandError):
            call_command("corideserver")

# Create your tests here.
