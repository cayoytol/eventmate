from django.contrib import admin
from .models import Category, Service, ServiceMedia


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name_ru', 'name_en', 'name_kz', 'slug', 'parent', 'icon')
    list_filter = ('parent',)
    search_fields = ('name_ru', 'name_en', 'name_kz', 'slug')
    prepopulated_fields = {'slug': ('name_ru',)}


class ServiceMediaInline(admin.TabularInline):
    model = ServiceMedia
    extra = 1
    fields = ('image', 'order')


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ('title', 'provider', 'category', 'price_amount', 'price_type', 'city', 'is_active', 'created_at')
    list_filter = ('is_active', 'price_type', 'category', 'city', 'created_at')
    search_fields = ('title', 'description', 'city')
    readonly_fields = ('created_at', 'updated_at')
    inlines = [ServiceMediaInline]
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('title', 'description', 'provider', 'category')
        }),
        ('Цена и местоположение', {
            'fields': ('price_amount', 'price_type', 'city')
        }),
        ('Обложка', {
            'fields': ('cover',)
        }),
        ('Статус', {
            'fields': ('is_active',)
        }),
        ('Системная информация', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
