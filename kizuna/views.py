from django.shortcuts import render


def module_page(request, title, hint):
    return render(
        request,
        "kizuna/module.html",
        {
            "title": title,
            "hint": hint,
        },
    )


def index(request):
    return module_page(
        request,
        "Kizuna",
        "Hackathon template bringing all modules together.",
    )
