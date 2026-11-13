from CORIDE.views import module_page


def index(request):
    return module_page(
        request,
        "Vehicules",
        "Enregistrement et verification des voitures.",
    )
