import time
from locust import HttpUser, task

class HelloWorldUser(HttpUser):
    @task
    def view_order(self):
        token_string = "TOKEN"

        self.client.get(
            "/orders",
            headers={"Authorization": "Bearer " + token_string},
        )
        time.sleep(0.5)
