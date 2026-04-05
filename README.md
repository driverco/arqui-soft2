Arquitectura de software Experimento 2

Comandos a ejecutar



kubectl apply -f database/postgres-secret.yaml
kubectl apply -f database/postgres-configmap.yaml
kubectl apply -f database/postgres-deploy.yaml
kubectl apply -f database/pgadmin-secret.yaml
kubectl apply -f database/pgadmin-deploy.yaml

minikube image build -t auth-service auth
minikube image load auth-service
kubectl apply -f auth/deployment.yaml
kubectl apply -f auth/service.yaml
minikube image build -t orders-service orders
minikube image load orders-service
kubectl apply -f orders/deployment.yaml
kubectl apply -f orders/service.yaml


kubectl rollout restart deployment auth-service
kubectl rollout restart deployment orders-service

Service           port
----------------------
postgres          5432
auth-service      8000
order-service     8010
admin-service     8020



