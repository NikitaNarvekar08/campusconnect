from django.db import migrations
from django.utils.text import slugify

CATEGORIES = ["Books", "Electronics", "Stationery", "Lab Equipment", "Other"]


def seed_categories(apps, schema_editor):
    Category = apps.get_model("listings", "Category")
    for name in CATEGORIES:
        Category.objects.get_or_create(name=name, defaults={"slug": slugify(name)})


class Migration(migrations.Migration):
    dependencies = [("listings", "0001_initial")]

    operations = [migrations.RunPython(seed_categories, migrations.RunPython.noop)]