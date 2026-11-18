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


MODULE_LINKS = [
    {"label": "M1", "url_name": "m1:index"},
    {"label": "M2", "url_name": "m2:index"},
    {"label": "M3", "url_name": "m3:index"},
    {"label": "M4", "url_name": "m4:index"},
    {"label": "M5", "url_name": "m5:index"},
]


def index(request):
    return render(
        request,
        "kizuna/home.html",
        {
            "title": "Kizuna",
            "hint": "Hackathon template bringing all modules together.",
            "modules": MODULE_LINKS,
        },
    )
