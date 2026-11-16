import django_filters

from accounts.models import Campus

from .models import Category, Listing


class ListingFilter(django_filters.FilterSet):
    category = django_filters.ModelMultipleChoiceFilter(
       field_name="category__slug", to_field_name="slug", queryset=Category.objects.all()
    )
    campus = django_filters.ModelMultipleChoiceFilter(
        field_name="campus", queryset=Campus.objects.all()
    )
    condition = django_filters.MultipleChoiceFilter(choices=Listing.Condition.choices)
    status = django_filters.MultipleChoiceFilter(choices=Listing.Status.choices)
    min_price = django_filters.NumberFilter(field_name="price", lookup_expr="gte")
    max_price = django_filters.NumberFilter(field_name="price", lookup_expr="lte")

    class Meta:
        model = Listing
        fields = []