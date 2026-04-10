Arquitectura de software Experimento 2

Comandos a ejecutar

minikube start --driver=docker
minikube dashboard &

minikube service pgadmin --url &


kubectl create serviceaccount my-app-sa

kubectl create rolebinding my-app-view-binding \
  --clusterrole=view \
  --serviceaccount=default:my-app-sa


kubectl create rolebinding my-app-admin-binding \
  --clusterrole=admin \
  --serviceaccount=default:my-app-sa

kubectl auth can-i list pods --as=system:serviceaccount:default:default


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

docker build -t apigateway-service apigateway
minikube image load apigateway-service
kubectl apply -f apigateway/deployment.yaml
kubectl apply -f apigateway/service.yaml

docker build -t analytics-service analytics
minikube image load analytics-service
kubectl apply -f analytics/deployment.yaml
kubectl apply -f analytics/service.yaml



kubectl rollout restart deployment auth-service
kubectl rollout restart deployment orders-service
kubectl rollout restart deployment adminkubes-service
kubectl rollout restart deployment apigateway-service
kubectl rollout restart deployment analytics-service

kubectl delete -n default deployment auth-service
kubectl delete -n default deployment orders-service
kubectl delete -n default deployment adminkubes-service
kubectl delete -n default deployment apigateway-service
kubectl delete -n default deployment analytics-service

minikube image rm auth-service
minikube image rm orders-service
minikube image rm adminkubes-service
minikube image rm apigateway-service
minikube image rm analytics-service

docker image rm auth-service
docker image rm orders-service
docker image rm adminkubes-service
docker image rm apigateway-service
docker image rm analytics-service



minikube service auth-service --url &
minikube service orders-service --url &
minikube service adminkubes-service --url &
minikube service apigateway-service &

Service           port
------------------------
postgres            5432
auth-service        8010
order-service       8020
admin-service       8030
apigateway-service  8040

# TODO

# DONE
- crear el test python(locust) con un caso de prueba
- crear el APIGATEWAY Y DESDE AHI LOGUIEAR TODAS LAS PETICIONES A LA BASE DE DATOS (dos deplyments o replicas)
- resolver problemas de permisos del write-pod adminkubes
- validacion de la idempotencia en las operaciones de escritura de base de datos
- ampliar el servicio de create order metiendo los items
- crear casos de prueba del servicio de orders (locust)
- crear el componente/servicio de analitica de seguridad
- modificar la presentacion
- videos de pruebas
- conclusiones del experimento

