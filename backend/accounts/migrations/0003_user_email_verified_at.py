from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("accounts", "0002_accountinvitation")]

    operations = [
        migrations.AddField(
            model_name="user",
            name="email_verified_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
