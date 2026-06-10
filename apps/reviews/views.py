from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, render
from django.utils.translation import gettext_lazy as _
from django.views.decorators.http import require_POST

from apps.catalog.models import Product

from .models import Review
from .utils import product_review_return_url


def _reviews_context(request: HttpRequest, product: Product, **extra: object) -> dict:
    reviews = product.reviews.filter(is_approved=True).select_related("customer")
    return {
        "product": product,
        "reviews": reviews,
        "review_return_url": product_review_return_url(request, product),
        **extra,
    }


def product_reviews_view(request: HttpRequest, product_id: int) -> HttpResponse:
    product = get_object_or_404(Product, pk=product_id)
    return render(request, "reviews/product_reviews.html", _reviews_context(request, product))


def _render_reviews_with_error(request: HttpRequest, product: Product, error: str) -> HttpResponse:
    """Re-render the full reviews container with an inline form error."""
    return render(
        request,
        "reviews/product_reviews.html",
        _reviews_context(request, product, form_error=error),
    )


@require_POST
def submit_review_view(request: HttpRequest, product_id: int) -> HttpResponse:
    product = get_object_or_404(Product, pk=product_id)

    if not request.user.is_authenticated:
        return _render_reviews_with_error(
            request,
            product,
            str(_("Увійдіть або зареєструйтесь, щоб залишити відгук.")),
        )

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

    customer = request.user
    review, created = Review.objects.get_or_create(
        product=product,
        customer=customer,
        defaults={
            "author_name": author_name,
            "rating": rating,
            "text": text,
            "is_approved": False,
        },
    )
    if not created:
        review.author_name = author_name
        review.rating = rating
        review.text = text
        review.is_approved = False
        review.save(update_fields=["author_name", "rating", "text", "is_approved"])

    return render(request, "reviews/submitted.html", {"product": product})
