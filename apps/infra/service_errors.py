from django.shortcuts import render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme


def service_unavailable(request, service):
    previous = request.META.get("HTTP_REFERER", "")
    if not url_has_allowed_host_and_scheme(previous, {request.get_host()}, require_https=request.is_secure()):
        previous = reverse("infra:datacenter")
    return render(
        request,
        "infra/service_unavailable.html",
        {"service": service, "back_url": previous},
        status=503,
    )
