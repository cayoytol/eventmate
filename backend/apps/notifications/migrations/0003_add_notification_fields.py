from django.db import migrations, models

class Migration(migrations.Migration):

    dependencies = [
        ('notifications', '0002_alter_notification_type'),
    ]

    operations = [
        migrations.AddField(
            model_name='notification',
            name='title',
            field=models.CharField(default='', max_length=200),
        ),
        migrations.AddField(
            model_name='notification',
            name='message',
            field=models.TextField(blank=True),
        ),
        migrations.AlterField(
            model_name='notification',
            name='type',
            field=models.CharField(choices=[
                ('new_request', 'New Request'),
                ('new_offer', 'New Offer'),
                ('offer_accepted', 'Offer Accepted'),
                ('offer_rejected', 'Offer Rejected'),
                ('order_created', 'Order Created'),
                ('order_paid', 'Order Paid'),
                ('order_completed', 'Order Completed'),
                ('new_review', 'New Review'),
                ('provider_reply', 'Provider Reply')
            ], max_length=20),
        ),
        migrations.AlterField(
            model_name='notification',
            name='payload',
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
