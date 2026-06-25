from django.contrib import admin
from .models import PortfolioItem, PortfolioMedia

class PortfolioMediaInline(admin.TabularInline):
    model = PortfolioMedia
    extra = 1

@admin.register(PortfolioItem)
class PortfolioItemAdmin(admin.ModelAdmin):
    list_display = ('id', 'title', 'provider_profile', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('title', 'description', 'provider_profile__user__email')
    inlines = [PortfolioMediaInline]

@admin.register(PortfolioMedia)
class PortfolioMediaAdmin(admin.ModelAdmin):
    list_display = ('id', 'item', 'media_type', 'created_at')
    list_filter = ('media_type',)
