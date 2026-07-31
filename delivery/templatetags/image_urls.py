import re

from django import template


register = template.Library()


@register.filter
def normalize_image_url(value):
    if not value:
        return value

    decoded = str(value)
    unicode_escape = re.compile(r'\\+u([0-9a-fA-F]{4})')
    while True:
        next_value = unicode_escape.sub(
            lambda match: chr(int(match.group(1), 16)),
            decoded,
        )
        if next_value == decoded:
            return decoded
        decoded = next_value
