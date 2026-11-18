from kizuna.views import module_page


def index(request):
    return module_page(
        request,
        "M4",
        "Placeholder page for module 4. Replace with your feature.",
    )
