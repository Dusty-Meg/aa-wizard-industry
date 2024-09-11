# Generated by Django 4.2.13 on 2024-09-11 08:07

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("wizardindustry", "0002_alter_baseprice_price"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="baseprice",
            name="price",
        ),
        migrations.AddField(
            model_name="baseprice",
            name="base_price",
            field=models.DecimalField(
                blank=True, decimal_places=2, max_digits=20, null=True
            ),
        ),
    ]
