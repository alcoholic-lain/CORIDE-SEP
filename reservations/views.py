from CORIDE.views import module_page


def index(request):
    return module_page(
        request,
        "Reservations",
        "Demandes de reservation, places disponibles et billets.",
    )
