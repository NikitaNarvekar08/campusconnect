import django_filters

from .models import ContactRequest


class ContactRequestFilter(django_filters.FilterSet):
    role = django_filters.ChoiceFilter(
        choices=[("sent", "Sent"), ("received", "Received")], method="filter_role"
    )
    status = django_filters.MultipleChoiceFilter(choices=ContactRequest.Status.choices)

    class Meta:
        model = ContactRequest
        fields = []

    def filter_role(self, queryset, name, value):
        user = self.request.user
        if value == "sent":
            return queryset.filter(requester=user)
        return queryset.filter(listing__seller=user)