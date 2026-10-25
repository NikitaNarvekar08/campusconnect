from rest_framework.pagination import PageNumberPagination


class ListingPagination(PageNumberPagination):
    page_size = 12
    page_size_query_param = "page_size"
    max_page_size = 48  # stops a client asking for the whole table at once
