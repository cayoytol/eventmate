from django.contrib import admin
from django.urls import path, include
from apps.accounts.views import UserProfileView, ProviderProfilePublicView, ProviderBlockView, ProviderUnblockView, UserAvatarView
from django.conf import settings
from django.conf.urls.static import static
from rest_framework import permissions
from drf_yasg.views import get_schema_view
from drf_yasg import openapi

schema_view = get_schema_view(
   openapi.Info(
      title="EventMate API",
      default_version='v1',
      description="API for EventMate Marketplace",
   ),
   public=True,
   permission_classes=(permissions.AllowAny,),
)

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/v1/auth/', include('apps.accounts.urls')),
    path('api/v1/', include('apps.accounts.availability_urls')),  # Availability CRUD
    # Alias for profile/me/ as required by frontend spec
    path('api/v1/profile/me/', UserProfileView.as_view(), name='profile_me_alias'),
    path('api/v1/profile/me/avatar/', UserAvatarView.as_view(), name='profile_me_avatar_alias'),
    path('api/v1/', include('apps.catalog.urls')),
    path('api/v1/', include('apps.marketplace.urls')),
    path('api/v1/plans/', include('apps.billing.plans_urls')),
    path('api/v1/billing/', include('apps.billing.billing_urls')),
    path('api/v1/payments/', include('apps.payments.urls')),
    path('api/v1/notifications/', include('apps.notifications.urls')),
    path('api/v1/portfolio/', include('apps.portfolio.urls')),
    path('api/v1/favorites/', include('apps.favorites.urls')),
    path('api/v1/comments/', include('apps.comments.urls')),
    path('api/v1/reports/', include('apps.reports.urls')),
    path('api/v1/ai/', include('apps.ai.urls')),
    path('api/v1/', include('apps.messaging.urls')),  # NEW
    
    # Requirement: GET /api/v1/services/{service_id}/comments/
    path('api/v1/services/<int:service_id>/comments/', 
         include(('apps.comments.urls', 'service-comments'), namespace='service-comments')),
    # Redundant but as per TZ requirement: GET /api/v1/providers/{id}/portfolio/
    path('api/v1/providers/', include('apps.portfolio.urls')),
    path('api/v1/providers/<int:pk>/', ProviderProfilePublicView.as_view(), name='provider-detail'),
    path('api/v1/providers/<int:pk>/block/', ProviderBlockView.as_view(), name='provider-block'),
    path('api/v1/providers/<int:pk>/unblock/', ProviderUnblockView.as_view(), name='provider-unblock'),
    
    # Swagger
    path('swagger/', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
