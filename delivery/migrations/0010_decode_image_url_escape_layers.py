import re

from django.db import migrations


def decode_image_url_escape_layers(apps, schema_editor):
    restaurant_model = apps.get_model('delivery', 'Restaurant')
    item_model = apps.get_model('delivery', 'Item')
    unicode_escape = re.compile(r'\\+u([0-9a-fA-F]{4})')

    for model in (restaurant_model, item_model):
        for record in model.objects.exclude(picture='').only('id', 'picture'):
            decoded = record.picture
            while True:
                next_value = unicode_escape.sub(
                    lambda match: chr(int(match.group(1), 16)),
                    decoded,
                )
                if next_value == decoded:
                    break
                decoded = next_value

            if decoded != record.picture:
                record.picture = decoded
                record.save(update_fields=['picture'])


class Migration(migrations.Migration):
    dependencies = [
        ('delivery', '0009_normalize_remaining_image_urls'),
    ]

    operations = [
        migrations.RunPython(decode_image_url_escape_layers, migrations.RunPython.noop),
    ]