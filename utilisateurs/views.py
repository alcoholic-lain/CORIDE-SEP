from CORIDE.views import module_page


def index(request):
    return module_page(
        request,
        "Utilisateurs",
        "Profils, inscriptions et verification des utilisateurs.",
    )
