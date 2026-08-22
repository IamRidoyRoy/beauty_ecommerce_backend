from rest_framework import serializers
from .models import ReportExport
from .selectors import REPORTS
class ReportExportSerializer(serializers.ModelSerializer):
    class Meta: model=ReportExport; fields=("id","report","params","status","file","error","created_at","updated_at"); read_only_fields=("status","file","error")
    def validate_report(self,value):
        if value not in REPORTS: raise serializers.ValidationError("Unknown report.")
        return value
