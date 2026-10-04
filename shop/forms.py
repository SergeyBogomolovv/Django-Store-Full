from django import forms
from django.utils import timezone

from .models import Coupon, Order, Review


class CartAddForm(forms.Form):
    quantity = forms.IntegerField(label="Количество", min_value=1, initial=1)
    update = forms.BooleanField(required=False, widget=forms.HiddenInput)


class CatalogFilterForm(forms.Form):
    q = forms.CharField(label="Поиск", required=False, max_length=200)
    min_price = forms.DecimalField(
        label="Цена от", required=False, min_value=0, max_digits=10, decimal_places=2
    )
    max_price = forms.DecimalField(
        label="Цена до", required=False, min_value=0, max_digits=10, decimal_places=2
    )
    sort = forms.ChoiceField(
        label="Сортировка",
        required=False,
        choices=[
            ("newest", "Сначала новинки"),
            ("price", "Сначала дешевле"),
            ("-price", "Сначала дороже"),
        ],
    )

    def clean(self):
        data = super().clean()
        low, high = data.get("min_price"), data.get("max_price")
        if low is not None and high is not None and low > high:
            self.add_error("max_price", "Верхняя цена должна быть не меньше нижней.")
        return data


class OrderCreateForm(forms.ModelForm):
    class Meta:
        model = Order
        fields = [
            "first_name",
            "last_name",
            "email",
            "phone",
            "delivery_method",
            "delivery_date",
            "city",
            "address",
            "postal_code",
            "payment_method",
        ]
        widgets = {
            "delivery_date": forms.DateInput(attrs={"type": "date"}),
            "phone": forms.TextInput(attrs={"placeholder": "8(999)123-45-67"}),
            "postal_code": forms.TextInput(attrs={"inputmode": "numeric"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["delivery_date"].widget.attrs["min"] = (
            timezone.localdate().isoformat()
        )

    def clean_delivery_date(self):
        date = self.cleaned_data["delivery_date"]
        if date < timezone.localdate():
            raise forms.ValidationError("Дата доставки не может быть в прошлом.")
        return date

    def clean(self):
        data = super().clean()
        if data.get("delivery_method") == Order.Delivery.COURIER:
            for field in ["city", "address", "postal_code"]:
                if not data.get(field):
                    self.add_error(field, "Заполните это поле для доставки курьером.")
        return data


class ReviewForm(forms.ModelForm):
    class Meta:
        model = Review
        fields = ["rating", "comment"]
        widgets = {
            "comment": forms.Textarea(
                attrs={"rows": 4, "placeholder": "Что вам понравилось в книге?"}
            ),
        }


class CouponApplyForm(forms.Form):
    code = forms.CharField(label="Промокод", max_length=30)

    def clean_code(self):
        code = self.cleaned_data["code"].strip().upper()
        coupon = Coupon.objects.filter(code=code).first()
        if not coupon or not coupon.is_valid():
            raise forms.ValidationError("Промокод не найден или больше не действует.")
        return code
