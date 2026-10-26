from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("memberships", "0006_memberfreeze"),
    ]

    operations = [
        migrations.AddField(
            model_name="membersubscription",
            name="reminder_sent_date",
            field=models.DateField(blank=True, null=True),
        ),
    ]
