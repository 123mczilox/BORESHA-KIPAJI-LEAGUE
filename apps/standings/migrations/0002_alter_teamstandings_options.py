from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('standings', '0001_initial'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='teamstandings',
            options={'ordering': ['-points']},
        ),
    ]