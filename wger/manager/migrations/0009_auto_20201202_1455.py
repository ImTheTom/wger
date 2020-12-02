# Generated by Django 3.1.3 on 2020-12-02 13:55

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('manager', '0008_auto_20190618_1617'),
    ]

    operations = [
        migrations.AddField(
            model_name='setting',
            name='rir',
            field=models.DecimalField(blank=True, choices=[(None, '------'), (0, 1), (0.5, 0.5), (1, 1), (1.5, 1.5), (2, 2), (2.5, 2.5), (3, 3), (3.5, 3.5), (4, 4)], decimal_places=1, max_digits=3, null=True, verbose_name='RiR'),
        ),
        migrations.AddField(
            model_name='workoutlog',
            name='rir',
            field=models.DecimalField(blank=True, choices=[(None, '------'), (0, 1), (0.5, 0.5), (1, 1), (1.5, 1.5), (2, 2), (2.5, 2.5), (3, 3), (3.5, 3.5), (4, 4)], decimal_places=1, max_digits=3, null=True, verbose_name='RiR'),
        ),
    ]
