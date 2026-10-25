from django.db import migrations

CATEGORIES = [
    ("Books", "books"),
    ("Electronics", "electronics"),
    ("Stationery", "stationery"),
    ("Lab Equipment", "lab-equipment"),
    ("Other", "other"),
]


def seed_categories(apps, schema_editor):
    Category = apps.get_model("listings", "Category")
    for name, slug in CATEGORIES:
        Category.objects.get_or_create(slug=slug, defaults={"name": name})


class Migration(migrations.Migration):
    dependencies = [("listings", "0001_initial")]
    operations = [migrations.RunPython(seed_categories, migrations.RunPython.noop)]
