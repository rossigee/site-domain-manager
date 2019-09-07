# Local development with Minikube

From the root of this repo, run up the minikube instance and deploy the resources...

```
minikube profile sdmgr
minikube start
kubectl apply -f k8s/minikube
```

At this point, you should have an empty database container and an app container running.

The app container should have created empty tables in the db container. There are various ways to check, including:

```
mysql -h$(minikube ip) -P30306 -usdmgr -psdmgr sdmgr -e "SHOW TABLES"
```

## Build the container to be tested

From root of the repo, build the container in the host...

```
docker build . -t sdmgr
```

Then, feed the new container image into minikube's docker engine:

```
docker save sdmgr | (eval $(minikube docker-env) && docker load)
```

Set minikube to use the new app container:

```
kubectl set image deployment/app app=sdmgr
kubectl delete pod -l app=sdmgr
```

## Self-signed TLS certificate

This stage is optional, and depends on whether you need an `https` endpoint for your needs or not (i.e. UI development).

Add the minikube IP to your `/etc/hosts` (use `minikube ip` to check correct address):

```
192.168.99.100 sdmgr.local
```

Create a self-signed SSL certificate, and deploy it to minikube.

```
openssl req -x509 -nodes -subj '/CN=sdmgr.local' -addext "subjectAltName = DNS:sdmgr.local" -newkey rsa:4096 -keyout privkey.pem -out cert.pem -days 365
kubectl create secret tls sdmgr-tls --key privkey.pem --cert cert.pem
```

Don't forget to add the `cert.pem` file as a 'authority' certificate to your browser too (i.e. via `chrome://settings/certificates?search=security`) trusted to identify websites to avoid CORS errors if you use the web UI.

Then, you should be all set to access the API via:

* (https://sdmgr.local/api/v1/docs)

Additionally, you should be able to access it via the UI:

* (https://sdmgr.local/)


# Proxy port for local development of UI

So, if you were to develop [the UI](https://github.com/rossigee/site-domain-manager-ui) locally, using `ng serve` to run on port 4200 or whatever, you would likely have CORS issues when the UI tries to connect back to the server using a non-localhost hostname.

There is a simple workaround, and that is to use `kubectl` to listen on a localhost port and proxy the requests to the API service in minikube directly. This can be achieved by running the following command in a spare terminal in the background:

```
kubectl port-forward service/api 8000
```

Then you should ensure the UI is configured (in `src/environments/environment.ts`) to use `http://localhost:8000/api/v1`.
