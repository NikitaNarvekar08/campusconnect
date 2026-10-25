import django_filters
from rest_framework.filters import OrderingFilter

from .models import Listing


class ListingFilter(django_filters.FilterSet):
    category = django_filters.CharFilter(field_name="category__slug")
    min_price = django_filters.NumberFilter(field_name="price", lookup_expr="gte")
    max_price = django_filters.NumberFilter(field_name="price", lookup_expr="lte")
    condition = django_filters.MultipleChoiceFilter(choices=Listing.Condition.choices)

    class Meta:
        model = Listing
        fields = []


class StableOrderingFilter(OrderingFilter):
    """Adds the id as a final tiebreaker so that listings with equal prices
    (or equal timestamps) never appear on two pages or get skipped."""

    def filter_queryset(self, request, queryset, view):
        queryset = super().filter_queryset(request, queryset, view)
        return queryset.order_by(*queryset.query.order_by, "-id")
