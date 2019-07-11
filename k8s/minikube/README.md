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

Kill the existing pod running the older container image.

```
kubectl delete pod -l workload=app
```

Add hostname to your `/etc/hosts`:

```
192.168.99.100 sdmgr.local
```

Create a self-signed SSL certificate, and deploy it to minikube.

```
openssl req -x509 -nodes -subj '/CN=sdmgr.local' -addext "subjectAltName = DNS:sdmgr.local" -newkey rsa:4096 -keyout privkey.pem -out cert.pem -days 365
kubectl create secret tls sdmgr-tls --key privkey.pem --cert cert.pem
```

Add it as a 'server' certificate to your browser too (i.e. via `chrome://settings`), to avoid CORS errors if you use the web UI.

Then, head on over to:

* (https://sdmgr.local/)
