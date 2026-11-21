from kizuna.views import module_page


def index(request):
    return module_page(
        request,
        "M1",
        "Placeholder page for module 1. Replace with your feature.",
    )
