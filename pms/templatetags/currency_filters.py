from django import template
from django.contrib.humanize.templatetags.humanize import intcomma

register = template.Library()

@register.filter
def idr_currency(value):
    """
    Format a number as Indonesian Rupiah currency.
    Usage: {{ room.rate|idr_currency }}
    """
    try:
        # Convert to float if it's a string or Decimal
        if isinstance(value, str):
            value = float(value)
        
        # Format with thousand separators and add IDR prefix
        formatted_value = intcomma(int(value))
        return f"Rp {formatted_value}"
    except (ValueError, TypeError):
        return value

@register.filter
def idr_currency_per_night(value):
    """
    Format a number as Indonesian Rupiah currency per night.
    Usage: {{ room.rate|idr_currency_per_night }}
    """
    try:
        # Convert to float if it's a string or Decimal
        if isinstance(value, str):
            value = float(value)
        
        # Format with thousand separators and add IDR prefix
        formatted_value = intcomma(int(value))
        return f"Rp {formatted_value}/night"
    except (ValueError, TypeError):
        return value