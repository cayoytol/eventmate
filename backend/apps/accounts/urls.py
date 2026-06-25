from django.urls import path
from .views import (
    RegisterView, CookieTokenObtainPairView, CookieTokenRefreshView, 
    LogoutView, UserProfileView, UserAvatarView,
    EmailSendVerifyView, EmailVerifyView,
    PhoneSendOtpView, PhoneVerifyOtpView
)

urlpatterns = [
    path('register/', RegisterView.as_view(), name='register'),
    path('login/', CookieTokenObtainPairView.as_view(), name='login'),
    path('refresh/', CookieTokenRefreshView.as_view(), name='refresh'),
    path('logout/', LogoutView.as_view(), name='logout'),
    
    path('profile/me/', UserProfileView.as_view(), name='profile_me'),
    path('profile/me/avatar/', UserAvatarView.as_view(), name='profile_me_avatar'),
    
    path('email/send-verify/', EmailSendVerifyView.as_view(), name='email_send_verify'),
    path('email/verify/', EmailVerifyView.as_view(), name='email_verify'),
    
    path('phone/send-otp/', PhoneSendOtpView.as_view(), name='phone_send_otp'),
    path('phone/verify-otp/', PhoneVerifyOtpView.as_view(), name='phone_verify_otp'),
]
