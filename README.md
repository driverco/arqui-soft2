Arquitectura de software Experimento 2

Comandos a ejecutar

minikube start --driver=docker
minikube dashboard &

minikube service pgadmin --url &





kubectl apply -f database/postgres-secret.yaml
kubectl apply -f database/postgres-configmap.yaml
kubectl apply -f database/postgres-deploy.yaml
kubectl apply -f database/pgadmin-secret.yaml
kubectl apply -f database/pgadmin-deploy.yaml

docker build -t auth-service auth
minikube image load auth-service
kubectl apply -f auth/deployment.yaml
kubectl apply -f auth/service.yaml

docker build -t orders-service orders
minikube image load orders-service
kubectl apply -f orders/deployment.yaml
kubectl apply -f orders/service.yaml

docker build -t adminkubes-service adminkubes
minikube image load adminkubes-service
kubectl apply -f adminkubes/deployment.yaml
kubectl apply -f adminkubes/service.yaml

kubectl rollout restart deployment auth-service
kubectl rollout restart deployment orders-service
kubectl rollout restart deployment adminkubes-service


minikube service auth-service --url &
minikube service orders-service --url &
minikube service adminkubes-service --url &

Service           port
----------------------
postgres          5432
auth-service      8010
order-service     8020
admin-service     8030


#TODO

- crear casos de prueba del servicio de orders (locust)
- crear el APIGATEWAY Y DESDE AHI LOGUIEAR TODAS LAS PETICIONES A LA BASE DE DATOS (dos deplyments o replicas)
(Juan) - ampliar el servicio de create order metiendo los items (Juan)
- metricas
- crear el componente/servicio de analitica de seguridad
(Wilmer) - resolver problemas de permisos del write-pod adminkubes
- validacion de la idempotencia en las operaciones de escritura de base de datos
(William) - modificar la presentacion
- *Grafana *Prometheus
- videos de pruebas
- conclusiones del experimento


