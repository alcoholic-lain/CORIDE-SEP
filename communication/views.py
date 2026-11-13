from CORIDE.views import module_page


def index(request):
    return module_page(
        request,
        "Communication",
        "Echanges et avis entre conducteurs et passagers.",
    )
