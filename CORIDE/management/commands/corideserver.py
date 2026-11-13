import ipaddress
import os
import socket

from django.conf import settings
from django.core.management import BaseCommand, CommandError, call_command
from zeroconf import IPVersion, ServiceInfo, Zeroconf


SERVICE_TYPE = "_coride._tcp.local."
SERVICE_NAME = "CoRide._coride._tcp.local."


def get_lan_address() -> str:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
            probe.connect(("192.0.2.1", 9))
            address = ipaddress.IPv4Address(probe.getsockname()[0])
    except (OSError, ValueError) as error:
        raise CommandError("Could not determine the computer's LAN IPv4 address.") from error

    if not address.is_private or address.is_loopback or address.is_link_local:
        raise CommandError("CoRide discovery requires a private IPv4 network.")

    return str(address)


class Command(BaseCommand):
    help = "Run Django and advertise CoRide for automatic Android discovery."

    def add_arguments(self, parser):
        parser.add_argument("--port", type=int, default=8000)
        parser.add_argument("--noreload", action="store_true")

    def handle(self, **options):
        if not settings.DEBUG:
            raise CommandError("The CoRide discovery server is for local DEBUG=True testing only.")

        port = options["port"]
        if not 1 <= port <= 65535:
            raise CommandError("The server port must be between 1 and 65535.")

        server_address = f"0.0.0.0:{port}"
        if not options["noreload"] and os.environ.get("RUN_MAIN") != "true":
            call_command("runserver", server_address, use_reloader=True)
            return

        address = get_lan_address()
        service = ServiceInfo(
            SERVICE_TYPE,
            SERVICE_NAME,
            addresses=[socket.inet_aton(address)],
            port=port,
            properties={"path": "/"},
            server=f"{socket.gethostname()}.local.",
        )

        with Zeroconf(interfaces=[address], ip_version=IPVersion.V4Only) as zeroconf:
            zeroconf.register_service(service)
            self.stdout.write(
                self.style.SUCCESS(
                    f"Advertising CoRide at http://{address}:{port} "
                    "for devices on this LAN."
                )
            )
            try:
                call_command("runserver", server_address, use_reloader=False)
            finally:
                zeroconf.unregister_service(service)
