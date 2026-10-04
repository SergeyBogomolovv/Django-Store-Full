from django import template

register = template.Library()


@register.filter
def rubles(value):
    return f"{value:,.2f}".replace(",", " ").replace(".", ",") + " ₽"


@register.simple_tag(takes_context=True)
def query_string(context, **kwargs):
    query = context["request"].GET.copy()
    query.update(kwargs)
    return query.urlencode()
