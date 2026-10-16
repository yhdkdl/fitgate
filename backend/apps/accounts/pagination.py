"""Pagination classes for accounts and audit log endpoints."""

from rest_framework.pagination import PageNumberPagination


class AuditLogPagination(PageNumberPagination):
    """Standard pagination for audit logs (page_size=20, max_page_size=100)."""

    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100
