from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render

from .models import BonusTransaction


@login_required
def bonus_view(request: HttpRequest) -> HttpResponse:
    transactions = BonusTransaction.objects.filter(customer=request.user).select_related("order")[:50]
    return render(request, "loyalty/bonus.html", {"transactions": transactions})
