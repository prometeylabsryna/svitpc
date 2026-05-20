from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, render
from django.utils.translation import gettext_lazy as _
from django.views.decorators.http import require_POST

from apps.catalog.models import Product

from .models import Review


def product_reviews_view(request: HttpRequest, product_id: int) -> HttpResponse:
    product = get_object_or_404(Product, pk=product_id)
    reviews = product.reviews.filter(is_approved=True).select_related("customer")
    return render(request, "reviews/product_reviews.html", {"product": product, "reviews": reviews})


def _render_reviews_with_error(request: HttpRequest, product: Product, error: str) -> HttpResponse:
    """Re-render the full reviews container with an inline form error."""
    reviews = product.reviews.filter(is_approved=True).select_related("customer")
    return render(
        request,
        "reviews/product_reviews.html",
        {"product": product, "reviews": reviews, "form_error": error},
    )


@require_POST
def submit_review_view(request: HttpRequest, product_id: int) -> HttpResponse:
    product = get_object_or_404(Product, pk=product_id)

    author_name = request.POST.get("author_name", "").strip()
    text = request.POST.get("text", "").strip()

    try:
        rating = int(request.POST.get("rating", ""))
        if not 1 <= rating <= 5:
            raise ValueError
    except (ValueError, TypeError):
        return _render_reviews_with_error(request, product, str(_("Оберіть оцінку від 1 до 5")))

    if not author_name or not text:
        return _render_reviews_with_error(request, product, str(_("Будь ласка, заповніть всі поля")))

    customer = request.user if request.user.is_authenticated else None

    # Prevent guest spam via session key (unique_together only protects logged-in users).
    if customer is None:
        session_key = f"reviewed_{product_id}"
        if request.session.get(session_key):
            return render(request, "reviews/submitted.html", {"product": product})
        request.session[session_key] = True

    Review.objects.get_or_create(
        product=product,
        customer=customer,
        defaults={
            "author_name": author_name,
            "rating": rating,
            "text": text,
            "is_approved": False,
        },
    )

    return render(request, "reviews/submitted.html", {"product": product})
