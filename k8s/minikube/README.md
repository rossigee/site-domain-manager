From root of the repo, build the container...

```
docker build . -t sdmgr
```

Run up the minikube instance...

```
minikube profile sdmgr
minikube start
minikube addons enable ingress
kubectl apply -f db.yml
kubectl apply -f app.yml
```

Also, db setup required:

```
kubectl exec -ti `kubectl get pods -l workload=db -o=jsonpath='{.items[0].metadata.name}'` sh
mysql -p$MYSQL_ROOT_PASSWORD
CREATE DATABASE sdmgr CHARACTER SET utf8;
GRANT ALL ON sdmgr.* TO sdmgr@'%' IDENTIFIED BY 'sdmgr';
```

Feed the docker image in:

```
docker save sdmgr | (eval $(minikube docker-env) && docker load)
```

Add hostname to your `/etc/hosts`:

```
192.168.99.100 sdmgr.local
```

Then, head on over to:

* (https://sdmgr.local/)

Ignore the SSL error (or fix it).
