from django.shortcuts import render


def module_page(request, title, hint):
    return render(
        request,
        "coride/module.html",
        {
            "title": title,
            "hint": hint,
        },
    )


def index(request):
    return module_page(
        request,
        "CoRide",
        "L'application de covoiturage qui rassemble tous les modules.",
    )
