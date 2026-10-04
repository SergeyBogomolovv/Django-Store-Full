from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import connection
from django.db.models import Avg, Q
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from .cart import Cart
from .forms import (
    CartAddForm,
    CatalogFilterForm,
    CouponApplyForm,
    OrderCreateForm,
    ReviewForm,
)
from .models import Category, Order, Product, Review, Wishlist
from .services import create_order


def wishlist_ids(request):
    if not request.user.is_authenticated:
        return set()
    return set(request.user.wishlist.values_list("product_id", flat=True))


def search_products(products, query):
    filters = (
        Q(name__icontains=query)
        | Q(description__icontains=query)
        | Q(author__icontains=query)
    )
    if connection.vendor == "sqlite":
        # SQLite LIKE не различает регистр только для латиницы.
        # Для небольшого локального каталога дополняем поиск через casefold.
        matching_ids = [
            product.pk
            for product in products
            if query.casefold()
            in " ".join([product.name, product.description, product.author]).casefold()
        ]
        filters |= Q(pk__in=matching_ids)
    return products.filter(filters)


def product_list(request, category_slug=None):
    category = (
        get_object_or_404(Category, slug=category_slug) if category_slug else None
    )
    categories = cache.get("catalog:categories")
    if categories is None:
        categories = list(Category.objects.all())
        cache.set("catalog:categories", categories, 60)

    form = CatalogFilterForm(request.GET)
    products = Product.objects.filter(available=True).select_related("category")
    if category:
        products = products.filter(category=category)
    if form.is_valid():
        data = form.cleaned_data
        if data["q"]:
            products = search_products(products, data["q"])
        if data["min_price"] is not None:
            products = products.filter(price__gte=data["min_price"])
        if data["max_price"] is not None:
            products = products.filter(price__lte=data["max_price"])
        sort = data["sort"] or "newest"
        products = products.order_by("-created" if sort == "newest" else sort, "-pk")
    else:
        products = products.none()

    # Кешируем популярную главную выдачу, но не корзину и не личные страницы.
    if not category and not any(request.GET.get(k) for k in form.fields):
        cached_products = cache.get("catalog:products")
        if cached_products is None:
            cached_products = list(products)
            cache.set("catalog:products", cached_products, 60)
        products = cached_products

    page = Paginator(products, 12).get_page(request.GET.get("page"))
    return render(
        request,
        "shop/product/list.html",
        {
            "category": category,
            "categories": categories,
            "page_obj": page,
            "filter_form": form,
            "wishlist_ids": wishlist_ids(request),
        },
    )


def can_review(user, product):
    return (
        user.is_authenticated
        and Order.objects.filter(
            user=user, status=Order.Status.COMPLETED, items__product=product
        ).exists()
    )


def product_detail(request, slug):
    product = get_object_or_404(Product, slug=slug, available=True)
    reviews = product.reviews.select_related("user")
    has_review = (
        request.user.is_authenticated and reviews.filter(user=request.user).exists()
    )
    return render(
        request,
        "shop/product/detail.html",
        {
            "product": product,
            "reviews": reviews,
            "average_rating": reviews.aggregate(value=Avg("rating"))["value"],
            "can_review": can_review(request.user, product) and not has_review,
            "has_review": has_review,
            "review_form": ReviewForm(),
            "wishlist_ids": wishlist_ids(request),
        },
    )


@require_POST
def cart_add(request, product_id):
    product = get_object_or_404(Product, pk=product_id)
    cart = Cart(request)
    form = CartAddForm(request.POST)
    error = None
    if form.is_valid():
        try:
            cart.add(product, **form.cleaned_data)
        except ValidationError as exc:
            error = exc.messages[0]
    else:
        error = "Укажите целое количество от 1."
    message = error or (
        "Количество обновлено."
        if form.cleaned_data.get("update")
        else "Товар успешно добавлен в корзину."
    )
    if request.headers.get("Accept") == "application/json":
        return JsonResponse(
            {"message": message, "cart_count": len(cart)}, status=400 if error else 200
        )
    if error:
        messages.error(request, message)
    else:
        messages.success(request, message)
    return redirect("shop:cart_detail")


@require_POST
def cart_remove(request, product_id):
    Cart(request).remove(product_id)
    messages.success(request, "Товар удалён из корзины.")
    return redirect("shop:cart_detail")


def cart_detail(request):
    cart = Cart(request)
    # Удалённую в админке книгу не оставляем невидимой позицией сессии.
    product_ids = {
        str(pk)
        for pk in Product.objects.filter(pk__in=cart.cart).values_list("pk", flat=True)
    }
    for product_id in list(cart.cart):
        if product_id not in product_ids:
            cart.remove(product_id)
            messages.info(request, "Удалённый товар убран из корзины.")
    return render(
        request,
        "shop/cart/detail.html",
        {"cart": cart, "coupon_form": CouponApplyForm()},
    )


@require_POST
def coupon_apply(request):
    form = CouponApplyForm(request.POST)
    if form.is_valid():
        request.session["coupon_code"] = form.cleaned_data["code"]
        messages.success(request, "Промокод применён.")
    else:
        messages.error(request, form.errors["code"][0])
    return redirect("shop:cart_detail")


@require_POST
def coupon_remove(request):
    request.session.pop("coupon_code", None)
    return redirect("shop:cart_detail")


def order_create(request):
    cart = Cart(request)
    if not cart:
        messages.info(request, "Сначала добавьте товары в корзину.")
        return redirect("shop:product_list")

    initial = {}
    if request.user.is_authenticated:
        name = request.user.full_name.split()
        initial = {
            "last_name": name[0] if name else "",
            "first_name": name[1] if len(name) > 1 else "",
            "email": request.user.email,
            "phone": request.user.phone,
        }
    form = OrderCreateForm(request.POST or None, initial=initial)
    if request.method == "POST" and form.is_valid():
        try:
            order = create_order(cart, form, request.user)
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            cart.clear()
            request.session["last_order_id"] = order.pk
            messages.success(request, f"Заказ №{order.pk} успешно оформлен.")
            return redirect("shop:order_created", order_id=order.pk)

    return render(request, "shop/order/create.html", {"form": form, "cart": cart})


def order_created(request, order_id):
    order = get_object_or_404(
        Order.objects.prefetch_related("items__product"), pk=order_id
    )
    owner = request.user.is_authenticated and order.user_id == request.user.pk
    if not owner and request.session.get("last_order_id") != order.pk:
        raise Http404
    return render(request, "shop/order/created.html", {"order": order})


@login_required
@require_POST
def review_add(request, product_id):
    product = get_object_or_404(Product, pk=product_id, available=True)
    if not can_review(request.user, product):
        messages.error(request, "Отзыв доступен после завершения вашего заказа.")
        return redirect(product)
    form = ReviewForm(request.POST)
    if form.is_valid():
        _, created = Review.objects.get_or_create(
            product=product, user=request.user, defaults=form.cleaned_data
        )
        if created:
            messages.success(request, "Спасибо за ваш отзыв!")
        else:
            messages.info(request, "Вы уже оставили отзыв на эту книгу.")
    else:
        for errors in form.errors.values():
            messages.error(request, errors[0])
    return redirect(product)


@login_required
def wishlist(request):
    products = Product.objects.filter(
        wishlist__user=request.user, available=True
    ).select_related("category")
    return render(
        request,
        "shop/wishlist.html",
        {"products": products, "wishlist_ids": wishlist_ids(request)},
    )


@login_required
@require_POST
def wishlist_toggle(request, product_id):
    product = get_object_or_404(Product, pk=product_id, available=True)
    item, created = Wishlist.objects.get_or_create(user=request.user, product=product)
    if not created:
        item.delete()
    messages.success(
        request,
        "Книга добавлена в избранное." if created else "Книга убрана из избранного.",
    )
    destination = request.POST.get("next", reverse("shop:wishlist"))
    if not url_has_allowed_host_and_scheme(destination, {request.get_host()}):
        destination = reverse("shop:wishlist")
    return redirect(destination)


def health(request):
    return JsonResponse({"status": "ok"})
