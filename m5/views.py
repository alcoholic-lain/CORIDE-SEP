from kizuna.views import module_page


def index(request):
    return module_page(
        request,
        "M5",
        "Placeholder page for module 5. Replace with your feature.",
    )
