from django.contrib import admin
from .models import EventRequest, Offer, Order, Review

@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ('id', 'order', 'client', 'provider_profile', 'rating', 'created_at')
    list_filter = ('rating', 'created_at')
    search_fields = ('client__email', 'provider_profile__user__email', 'text')
    readonly_fields = ('created_at',)

@admin.register(EventRequest)
class EventRequestAdmin(admin.ModelAdmin):
    list_display = ('id', 'client', 'category', 'city', 'event_date', 'status', 'created_at')
    list_filter = ('status', 'city', 'category')
    search_fields = ('client__email', 'description')

@admin.register(Offer)
class OfferAdmin(admin.ModelAdmin):
    list_display = ('id', 'request', 'provider_profile', 'price', 'status', 'created_at')
    list_filter = ('status',)
    search_fields = ('provider_profile__user__email',)

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'client', 'provider_profile', 'status', 'price_agreed', 'created_at')
    list_filter = ('status',)
    search_fields = ('client__email', 'provider_profile__user__email')
