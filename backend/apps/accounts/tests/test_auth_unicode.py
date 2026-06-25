"""
Test auth endpoints with Unicode characters to ensure no UnicodeEncodeError
"""
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status
from django.contrib.auth import get_user_model

User = get_user_model()


class AuthUnicodeHeaderTest(TestCase):
    """Test that auth endpoints handle Unicode without UnicodeEncodeError in headers"""
    
    def setUp(self):
        self.client = APIClient()
        
        # Create user with Unicode username (ASCII email per RFC)
        self.user = User.objects.create_user(
            email='test@example.com',
            username='Иван_Тестовый',  # Cyrillic username
            password='testpass123',
            role='client'
        )
    
    def test_login_response_headers_are_ascii(self):
        """All response headers from login must be ASCII-safe"""
        response = self.client.post('/api/v1/auth/login/', {
            'email': 'test@example.com',
            'password': 'testpass123'
        })
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Check all headers are ASCII
        for header_name, header_value in response.items():
            with self.subTest(header=header_name):
                try:
                    # HTTP headers must be ASCII (Latin-1)
                    str(header_value).encode('ascii')
                except (UnicodeEncodeError, AttributeError) as e:
                    self.fail(
                        f"Header '{header_name}' contains non-ASCII: {header_value!r}\n"
                        f"Error: {e}"
                    )
    
    def test_refresh_no_unicode_encode_error(self):
        """Refresh token should not raise UnicodeEncodeError (Windows/wsgiref)"""
        # Login to get refresh token in cookie
        response = self.client.post('/api/v1/auth/login/', {
            'email': 'test@example.com',
            'password': 'testpass123'
        })
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('refresh_token', response.cookies)
        
        # Try refresh - should not crash with UnicodeEncodeError
        response2 = self.client.post('/api/v1/auth/refresh/')
        
        # Should succeed (200) or fail gracefully (400/401), but NOT 500
        self.assertIn(
            response2.status_code, 
            [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST, status.HTTP_401_UNAUTHORIZED],
            f"Unexpected status: {response2.status_code}"
        )
    
    def test_refresh_response_headers_are_ascii(self):
        """All response headers from refresh must be ASCII-safe"""
        # Login
        response = self.client.post('/api/v1/auth/login/', {
            'email': 'test@example.com',
            'password': 'testpass123'
        })
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Refresh
        response2 = self.client.post('/api/v1/auth/refresh/')
        
        # Check all headers are ASCII
        for header_name, header_value in response2.items():
            with self.subTest(header=header_name):
                try:
                    str(header_value).encode('ascii')
                except (UnicodeEncodeError, AttributeError) as e:
                    self.fail(
                        f"Header '{header_name}' contains non-ASCII: {header_value!r}\n"
                        f"Error: {e}"
                    )
    
    def test_refresh_cookies_are_ascii(self):
        """All cookies from refresh must be ASCII-safe"""
        # Login
        response = self.client.post('/api/v1/auth/login/', {
            'email': 'test@example.com',
            'password': 'testpass123'
        })
        
        # Refresh
        response2 = self.client.post('/api/v1/auth/refresh/')
        
        # Check all cookies are ASCII
        for cookie_name, cookie_obj in response2.cookies.items():
            with self.subTest(cookie=cookie_name):
                try:
                    # Check cookie name
                    cookie_name.encode('ascii')
                    # Check cookie value
                    cookie_obj.value.encode('ascii')
                except (UnicodeEncodeError, AttributeError) as e:
                    self.fail(
                        f"Cookie '{cookie_name}' contains non-ASCII\n"
                        f"Value: {cookie_obj.value!r}\n"
                        f"Error: {e}"
                    )
