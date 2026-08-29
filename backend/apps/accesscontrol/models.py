from django.db import models


class StaffDashboardAccess(models.Model):
    # Intentionally stores the numeric user id instead of a ForeignKey. The original
    # project predates committed accounts migrations, so this keeps the new migration
    # independent and safe for existing installations.
    user_id = models.PositiveBigIntegerField(unique=True, db_index=True)
    modules = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("user_id",)

    def __str__(self):
        return f"Dashboard access for user #{self.user_id}"
