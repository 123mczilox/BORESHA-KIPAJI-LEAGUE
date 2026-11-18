from django.db import migrations, models


def mark_existing_performances_as_appearances(apps, schema_editor):
    performance_model = apps.get_model(
        'statistics',
        'PlayerMatchPerformance',
    )
    performance_model.objects.using(
        schema_editor.connection.alias,
    ).update(appeared=True)


class Migration(migrations.Migration):

    dependencies = [
        ('statistics', '0002_playermatchperformance_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='playermatchperformance',
            name='appeared',
            field=models.BooleanField(default=False),
        ),
        migrations.RunPython(
            mark_existing_performances_as_appearances,
            migrations.RunPython.noop,
        ),
    ]