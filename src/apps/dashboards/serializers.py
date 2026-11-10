from rest_framework import serializers

from .models import ReportSnapshot


class ReportSnapshotSerializer(serializers.ModelSerializer):
    created_by_name = serializers.CharField(source="created_by.display_name", read_only=True, allow_null=True)
    created_by_id = serializers.UUIDField(read_only=True, allow_null=True)
    site_name = serializers.CharField(source="site.name", read_only=True, allow_null=True)
    site_id = serializers.UUIDField(read_only=True, allow_null=True)

    class Meta:
        model = ReportSnapshot
        fields = [
            "id",
            "snapshot_type",
            "section",
            "period_start",
            "period_end",
            "site_id",
            "site_name",
            "metrics",
            "created_by_id",
            "created_by_name",
            "notes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class GenerateSnapshotSerializer(serializers.Serializer):
    snapshot_type = serializers.ChoiceField(
        choices=ReportSnapshot.SnapshotType.choices,
        default=ReportSnapshot.SnapshotType.DAILY,
    )
    section = serializers.ChoiceField(
        choices=ReportSnapshot.Section.choices,
        default=ReportSnapshot.Section.OPERATIONS,
    )
    period_start = serializers.DateField()
    period_end = serializers.DateField()
    site_id = serializers.UUIDField(required=False, allow_null=True)
    notes = serializers.CharField(required=False, allow_blank=True, max_length=500)
