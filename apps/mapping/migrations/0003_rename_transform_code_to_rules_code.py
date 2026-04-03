from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('mapping', '0002_conversionjob_function_name_and_more'),
    ]

    operations = [
        migrations.RenameField(
            model_name='conversionjob',
            old_name='transform_code',
            new_name='rules_code',
        ),
        migrations.AlterField(
            model_name='conversionjob',
            name='direction',
            field=models.CharField(
                choices=[('json_to_csv', 'JSON to CSV'), ('csv_to_json', 'CSV to JSON')],
                max_length=20,
            ),
        ),
    ]
