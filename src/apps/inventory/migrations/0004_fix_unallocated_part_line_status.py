from django.db import migrations


def fix_unallocated_part_line_status(apps, schema_editor):
    WorkOrderPart = apps.get_model("inventory", "WorkOrderPart")
    # Repair unallocated part lines that were automatically marked CANCELLED
    # on work orders that were not cancelled.
    WorkOrderPart.objects.filter(
        status="CANCELLED",
        quantity_issued=0,
        quantity_consumed=0,
    ).exclude(work_order__status="CANCELLED").update(status="REQUESTED")


def reverse_fix(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("inventory", "0003_alter_stockmovement_movement_type"),
    ]

    operations = [
        migrations.RunPython(fix_unallocated_part_line_status, reverse_code=reverse_fix),
    ]
