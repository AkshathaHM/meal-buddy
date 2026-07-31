import re

from django.db import migrations


def decode_remaining_image_urls(apps, schema_editor):
    restaurant_model = apps.get_model('delivery', 'Restaurant')
    item_model = apps.get_model('delivery', 'Item')

    for model in (restaurant_model, item_model):
        for record in model.objects.exclude(picture='').only('id', 'picture'):
            decoded = re.sub(
                r'\\+u([0-9a-fA-F]{4})',
                lambda match: chr(int(match.group(1), 16)),
                record.picture,
            )
            if decoded != record.picture:
                record.picture = decoded
                record.save(update_fields=['picture'])


class Migration(migrations.Migration):
    dependencies = [
        ('delivery', '0008_normalize_image_urls'),
    ]

    operations = [
        migrations.RunPython(decode_remaining_image_urls, migrations.RunPython.noop),
    ]