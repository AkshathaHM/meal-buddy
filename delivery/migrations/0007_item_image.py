from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('delivery', '0006_order_orderitem'),
    ]

    operations = [
        migrations.AddField(
            model_name='item',
            name='image',
            field=models.ImageField(blank=True, null=True, upload_to='menu_items/'),
        ),
    ]