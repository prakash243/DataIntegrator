from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('mapping', '0003_rename_transform_code_to_rules_code'),
    ]

    operations = [
        migrations.AlterField(
            model_name='conversionjob',
            name='direction',
            field=models.CharField(
                choices=[
                    ('json_to_csv', 'JSON to CSV'),
                    ('csv_to_json', 'CSV to JSON'),
                    ('edi_to_json', 'EDI to JSON'),
                    ('edi_to_csv', 'EDI to CSV'),
                ],
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name='conversionjob',
            name='edi_transaction_set',
            field=models.CharField(blank=True, default='', max_length=10),
        ),
    ]
