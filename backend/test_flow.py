import requests
import time

BASE_URL = "http://localhost:8000/api/v1"

def test_flow():
    session_p = requests.Session()
    session_c = requests.Session()
    
    print("1) Login as Provider")
    # assuming provider1@test.com / provider1pass
    r = session_p.post(f"{BASE_URL}/accounts/login/", json={
        "email": "provider1@test.com", "password": "password123"
    })
    if r.status_code != 200:
        print("Login failed, maybe need to create users. Let's try to register.")
        r = session_p.post(f"{BASE_URL}/accounts/register/", json={
            "email": "provider1@test.com", "password": "password123", "role": "provider"
        })
        if r.status_code != 201:
            print("Register failed:", r.json())
        r = session_p.post(f"{BASE_URL}/accounts/login/", json={
            "email": "provider1@test.com", "password": "password123"
        })
    print("Provider login:", r.status_code)
    
    print("6) Login as Client")
    r = session_c.post(f"{BASE_URL}/accounts/login/", json={
        "email": "client1@test.com", "password": "password123"
    })
    if r.status_code != 200:
        r = session_c.post(f"{BASE_URL}/accounts/register/", json={
            "email": "client1@test.com", "password": "password123", "role": "client"
        })
        r = session_c.post(f"{BASE_URL}/accounts/login/", json={
            "email": "client1@test.com", "password": "password123"
        })
    print("Client login:", r.status_code)
    
    print("2) Create active service")
    # need category
    cats = session_p.get(f"{BASE_URL}/categories/")
    cat_id = 1
    if cats.status_code == 200 and cats.json():
        cat_id = cats.json()[0]['id']
        
    r = session_p.post(f"{BASE_URL}/services/", json={
        "title": "QA Test Service",
        "category": cat_id,
        "description": "Test",
        "price_amount": "5000",
        "price_type": "fixed",
        "city": "Almaty",
        "is_active": True
    })
    print("Create service:", r.status_code, r.text)
    service_id = r.json().get('id')
    
    print("3) Check service in /provider/services/")
    r = session_p.get(f"{BASE_URL}/services/?provider=me")
    print("Provider services count:", len(r.json().get('results', r.json())))
    
    print("4) Check service in catalog")
    r = session_c.get(f"{BASE_URL}/services/")
    print("Catalog services count:", len(r.json().get('results', r.json())))
    
    print("5) Open service detail")
    r = session_c.get(f"{BASE_URL}/services/{service_id}/")
    print("Service detail:", r.status_code)
    
    print("7) Send request/contact")
    r = session_c.post(f"{BASE_URL}/requests/", json={
        "title": "Need QA Test Service",
        "description": "Test request",
        "category": cat_id,
        "city": "Almaty",
        "event_date": "2026-10-10",
        "budget_min": 1000,
        "budget_max": 5000,
        "target_provider": session_p.get(f"{BASE_URL}/accounts/me/").json()['provider_profile']['id'],
        "target_service": service_id
    })
    print("Create request:", r.status_code, r.text)
    req_id = r.json().get('id')
    
    print("8) Provider opens requests")
    r = session_p.get(f"{BASE_URL}/requests/")
    print("Provider requests count:", len(r.json().get('results', r.json())))
    
    print("9) Provider sends offer")
    r = session_p.post(f"{BASE_URL}/offers/", json={
        "request": req_id,
        "service": service_id,
        "price_amount": "5000",
        "message": "I can do this"
    })
    print("Create offer:", r.status_code, r.text)
    offer_id = r.json().get('id')
    
    print("10) Client opens request")
    r = session_c.get(f"{BASE_URL}/requests/{req_id}/")
    print("Client request detail:", r.status_code)
    
    print("11) Client accepts offer")
    r = session_c.post(f"{BASE_URL}/offers/{offer_id}/accept/")
    print("Accept offer:", r.status_code, r.text)
    
    print("12) Order created check")
    r = session_c.get(f"{BASE_URL}/orders/")
    orders = r.json().get('results', r.json())
    print("Client orders count:", len(orders))
    order_id = orders[0]['id'] if orders else None
    
    print("13) Client opens order")
    r = session_c.get(f"{BASE_URL}/orders/{order_id}/")
    print("Client order detail:", r.status_code, "status:", r.json().get('status'), "payment_status:", r.json().get('payment_status'))
    
    print("14) Mock pay")
    r = session_c.post(f"{BASE_URL}/orders/{order_id}/mock_pay/")
    print("Mock pay:", r.status_code, r.text)
    
    print("15) Client views QR")
    r = session_c.get(f"{BASE_URL}/orders/{order_id}/")
    print("Order after pay:", r.json().get('payment_status'), "start_token:", r.json().get('start_token'))
    start_token = r.json().get('start_token')
    finish_token = r.json().get('finish_token')
    
    print("16) Provider opens order")
    r = session_p.get(f"{BASE_URL}/orders/{order_id}/")
    print("Provider order:", r.status_code)
    
    print("17) Provider check-in")
    r = session_p.post(f"{BASE_URL}/orders/{order_id}/check_in/", json={"token": start_token})
    print("Check-in:", r.status_code, r.text)
    
    print("18) Provider complete")
    r = session_p.post(f"{BASE_URL}/orders/{order_id}/complete/", json={"token": finish_token})
    print("Complete:", r.status_code, r.text)

if __name__ == '__main__':
    test_flow()
