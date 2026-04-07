import time
from locust import HttpUser, task

class HelloWorldUser(HttpUser):
    @task
    def view_order(self):
        token_string = "TOKEN"

        self.client.get(
            "/orders",
            headers={"Authorization": "Bearer " + token_string, "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"},
        )
        time.sleep(0.2)
