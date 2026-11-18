from kizuna.views import module_page


def index(request):
    return module_page(
        request,
        "M2",
        "Placeholder page for module 2. Replace with your feature.",
    )
