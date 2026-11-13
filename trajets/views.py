from CORIDE.views import module_page


def index(request):
    return module_page(
        request,
        "Trajets",
        "Publication et recherche de trajets de covoiturage.",
    )
