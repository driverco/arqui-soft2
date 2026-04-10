from random import random
import time
from locust import HttpUser, task

# class TestOrders(HttpUser):
#     @task
#     def view_order(self):
#         token_string = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJzdXBlcnZpc29yMSIsInJvbGUiOiJTIiwiZXhwIjoxNzc1NTQ2NTIyfQ.kHYzB8zJw7l39ODW5JxDm-BtBDUzUvNI5EA-cqxvbuQ"
#         user_agent = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        
#         if (random() > 0.8):   # 90% True, 10% False
#             user_agent = "phising-bot/1.0"
#         self.client.get(
#             "/api/orders/orders",
#             headers={"Authorization": "Bearer " + token_string, "User-Agent": user_agent},
#         )

class TestOrders(HttpUser):
    @task
    def view_order(self):
        payload = {
            "user_id": 31,
            "client_id": 32,
            "items": [
                {
                    "item_id": 37, 
                    "quantity": 2,
                    "unit_value": 200
                },
                {
                    "item_id": 38, 
                    "quantity": 3, 
                    "unit_value": 300
                },
                {
                    "item_id": 43, 
                    "quantity": 4, 
                    "unit_value": 400
                }
            ]
        }

        headers = {
            "Authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJzYWxlczEiLCJyb2xlIjoiVSIsImV4cCI6MTc3NTc5MDQ2NH0.s1sGOSJnUGSjAuQa065h4HVEo5OBMYud3nLCc86vWtY",
            "Content-Type": "application/json"
        }

        self.client.post(
            "/api/orders/orders", 
            json=payload, 
            headers=headers
        )