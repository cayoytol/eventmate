from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status

User = get_user_model()

class RegistrationPasswordSecurityTest(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_weak_password_registration_fails(self):
        response = self.client.post('/api/v1/auth/register/', {
            'email': 'weak@example.com',
            'username': 'weakuser',
            'password': '123',  # weak / short password
            'role': 'client'
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('password', response.data)

    def test_valid_password_registration_succeeds(self):
        response = self.client.post('/api/v1/auth/register/', {
            'email': 'strong@example.com',
            'username': 'stronguser',
            'password': 'StrongPass123!',
            'role': 'client'
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(User.objects.filter(email='strong@example.com').exists())
