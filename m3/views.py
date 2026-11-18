from kizuna.views import module_page


def index(request):
    return module_page(
        request,
        "M3",
        "Placeholder page for module 3. Replace with your feature.",
    )
