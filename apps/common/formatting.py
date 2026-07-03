"""Shared presentation helpers for API responses."""

from django.utils import timezone
from django.utils.formats import date_format


def format_local_date(value):
    if value is None:
        return None
    return date_format(value, "N j, Y")


def format_local_datetime(value):
    if value is None:
        return None
    return date_format(timezone.localtime(value), "N j, Y g:i A")