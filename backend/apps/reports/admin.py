from django.contrib import admin
from .models import Report

@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'reporter', 'content_type', 'object_id', 
        'reason', 'status', 'created_at'
    )
    list_filter = ('status', 'reason', 'content_type', 'created_at')
    search_fields = ('reporter__email', 'message', 'resolution_note')
    readonly_fields = ('reporter', 'content_type', 'object_id', 'created_at')
    
    fieldsets = (
        ('Report Details', {
            'fields': ('reporter', 'content_type', 'object_id', 'reason', 'message', 'created_at')
        }),
        ('Resolution', {
            'fields': ('status', 'resolution_note', 'resolved_at', 'resolved_by')
        }),
    )
