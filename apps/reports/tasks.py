import csv
from io import StringIO
from django.core.files.base import ContentFile
from celery import shared_task
from .models import ReportExport
from .selectors import REPORTS
@shared_task
def export_report(export_id):
    export=ReportExport.objects.get(pk=export_id); export.status=ReportExport.Status.PROCESSING; export.save(update_fields=["status","updated_at"])
    try:
        result=REPORTS[export.report](export.params)
        rows=result if isinstance(result,list) else [result]
        keys=sorted({k for row in rows if isinstance(row,dict) for k in row.keys()}); out=StringIO(); writer=csv.DictWriter(out,fieldnames=keys); writer.writeheader()
        for row in rows: writer.writerow({k:row.get(k,"") for k in keys})
        export.file.save(f"{export.report}-{export.id}.csv",ContentFile(out.getvalue().encode("utf-8")),save=False); export.status=ReportExport.Status.COMPLETED; export.save(update_fields=["file","status","updated_at"])
    except Exception as exc:
        export.status=ReportExport.Status.FAILED; export.error=str(exc); export.save(update_fields=["status","error","updated_at"]); raise
    return export.id
