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

@register.filter
def hex_to_rgb(hex_color):
    """
    Convert hex color to RGB values.
    Usage: {{ device_state.rgb_color|hex_to_rgb }}
    Returns a dictionary with 'r', 'g', 'b' keys
    """
    try:
        hex_color = hex_color.lstrip('#')
        if len(hex_color) == 6:
            r = int(hex_color[0:2], 16)
            g = int(hex_color[2:4], 16)
            b = int(hex_color[4:6], 16)
            return {'r': r, 'g': g, 'b': b}
        return {'r': 255, 'g': 255, 'b': 255}  # Default to white
    except (ValueError, TypeError):
        return {'r': 255, 'g': 255, 'b': 255}  # Default to white