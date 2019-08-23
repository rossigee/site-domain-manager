from ..base import WAFProviderAgent

import logging
_logger = logging.getLogger(__name__)

import os
import asyncio
import uuid
import kubernetes
import json
import yaml

from .mime import MIME_TYPES
from .nginx import NGINX_CONF_TPL


class K8S(WAFProviderAgent):
    def __init__(self, data):
        WAFProviderAgent.__init__(self, data)
        _logger.info(f"Loading Kubernetes WAF provider agent (id: {self.id}): {self.label}")

        # TODO: a better mechanism as this prevents configuration of multiple
        # WAF targets
        k8s_config = kubernetes.client.Configuration()
        k8s_config.host = os.getenv('K8S_API_URL')
        k8s_config.api_key = {"authorization": "Bearer " + os.getenv('K8S_API_TOKEN')}
        k8s_config.verify_ssl = False
        self.namespace = os.getenv('K8S_WAF_NAMESPACE')
        self.context = os.getenv('K8S_WAF_CONTEXT')

        self.api_client = kubernetes.client.ApiClient(k8s_config)
        self.apps_v1 = kubernetes.client.AppsV1beta2Api(self.api_client)
        self.core_v1 = kubernetes.client.CoreV1Api(self.api_client)
        self.ext_v1 = kubernetes.client.ExtensionsV1beta1Api(self.api_client)

    async def _load_state(self):
        await super(K8S, self)._load_state()
        try:
            # TODO: deserialise the values somehow
            self.configmaps = self.state['configmaps']
            self.daemonsets = self.state['daemonsets']
            self.services = self.state['services']
            self.ingresses = self.state['ingresses']
            self.certs = self.state['certs']
            _logger.info(f"Restored state for {self.label} with {len(self.daemonsets)} daemonsets.")
        except:
            self.configmaps = {}
            self.daemonsets = {}
            self.services = {}
            self.ingresses = {}
            self.certs = {}
            _logger.info(f"Initialised state for {self.label}.")

    async def _save_state(self):
        self.state = {
            "configmaps": self.configmaps,
            "daemonsets": self.daemonsets,
            "services": self.services,
            "ingresses": self.ingresses,
            "certs": self.certs
        }
        await super(K8S, self)._save_state()

    async def start(self):
        try:
            _logger.debug(f"Starting K8S WAF provider agent (id: {self.id}).")
            await self._load_state()

        except Exception as e:
            _logger.exception(e)

    async def _check_mime_types_config_map(self):
        try:
            # Fetch configmap
            ret = self.core_v1.list_namespaced_config_map(self.namespace)
            for c in ret.items:
                if c.metadata.name == "mimetypes":
                    _logger.debug("MIME types configmap already exists.")
                    return

            # Create configmap
            _logger.info(f"Creating MIME types configmap...")
            body = kubernetes.client.V1ConfigMap(
                metadata = kubernetes.client.V1ObjectMeta(name="mimetypes"),
                data = {
                    "mime.types": MIME_TYPES,
                }
            )
            self.core_v1.create_namespaced_config_map(self.namespace, body)

        except Exception as e:
            _logger.exception(e)

    async def refresh(self):
        _logger.info(f"Checking presence of 'mimetypes' config map")
        await self._check_mime_types_config_map()

        _logger.info(f"Refreshing list of domains managed on {self.label}...")
        configmaps = {}
        daemonsets = {}
        services = {}
        ingresses = {}
        certs = {}

        try:
            _logger.info(f"Fetching configmaps in namespace '{self.namespace}'...")
            ret = self.core_v1.list_namespaced_config_map(self.namespace)
            configmaps = [self.api_client.sanitize_for_serialization(o) for o in ret.items]

            _logger.info(f"Fetching daemonsets in namespace '{self.namespace}'...")
            ret = self.apps_v1.list_namespaced_daemon_set(self.namespace)
            daemonsets = [self.api_client.sanitize_for_serialization(o) for o in ret.items]

            _logger.info(f"Fetching services in namespace '{self.namespace}'...")
            ret = self.core_v1.list_namespaced_service(self.namespace)
            services = [self.api_client.sanitize_for_serialization(o) for o in ret.items]

            _logger.info(f"Fetching ingresses in namespace '{self.namespace}'...")
            ret = self.ext_v1.list_namespaced_ingress(self.namespace)
            ingresses = [self.api_client.sanitize_for_serialization(o) for o in ret.items]

            #_logger.info(f"Fetching certs in namespace '{self.namespace}'...")
            #ret = #self.ext_v1.list_namespaced_certificates(self.namespace)
            #certs = ret.items

            self.configmaps = configmaps
            self.daemonsets = daemonsets
            self.services = services
            self.ingresses = ingresses
            self.certs = certs

            await self._save_state()

        except Exception as e:
            _logger.exception(e)
            return str(e)

        return "OK"

    async def apply_configuration(self, sitename, hostname, aliases, ip_addrs):
        daemonset = None

        # Generate a siteid that isn't a domain name (for clarity)
        siteid = sitename.split(".")[0]

        # Create configmap
        _logger.debug(f"Creating configmap for nginx proxy daemonset '{siteid}'...")
        nginx_conf = NGINX_CONF_TPL
        nginx_conf = nginx_conf.replace("{{aliases}}", " ".join(aliases + [hostname]))
        nginx_conf = nginx_conf.replace("{{hostingip1}}", ip_addrs[0])
        nginx_configmap = kubernetes.client.V1ConfigMap(
            metadata = kubernetes.client.V1ObjectMeta(name=siteid),
            data = {
                "nginx.conf": nginx_conf
            }
        )

        try:
            for d in self.daemonsets:
                if d['metadata']['name'] == siteid:
                    daemonset = d
                    break

            if daemonset is not None:
                # Update domains listed in configmap
                _logger.info(f"Updating nginx proxy config map for '{siteid}'...")
                self.core_v1.replace_namespaced_config_map(siteid, self.namespace, nginx_configmap)

                # Restart daemonset
                _logger.info(f"Restarting nginx proxy daemonset '{siteid}'...")
                label_selector = f"workload=proxy-{siteid}"
                response = self.core_v1.list_namespaced_pod(self.namespace, label_selector=label_selector)
                podlist = [x.metadata.name for x in response.items]
                print(podlist)
                for p in podlist:
                    p_resp = kubernetes.stream.stream(
                        self.core_v1.connect_get_namespaced_pod_exec,
                        p, self.namespace, command=["kill", "-HUP", "1"]
                    )
                    print(p_resp)

            else:
                _logger.info(f"Creating nginx proxy config map for '{siteid}'...")
                api_response = self.core_v1.create_namespaced_config_map(self.namespace, nginx_configmap)

                # Create daemonset
                _logger.info(f"Creating nginx proxy daemonset '{siteid}'...")
                body = kubernetes.client.V1beta2DaemonSet(
                    metadata = kubernetes.client.V1ObjectMeta(name=siteid),
                    spec = kubernetes.client.V1beta2DaemonSetSpec(
                        selector = kubernetes.client.V1LabelSelector(
                            match_labels = {
                                "workload": f"proxy-{siteid}"
                            }
                        ),
                        template = kubernetes.client.V1PodTemplateSpec(
                            metadata = kubernetes.client.V1ObjectMeta(
                                #name = hostname,
                                labels = {
                                    "workload": f"proxy-{siteid}"
                                }
                            ),
                            spec = kubernetes.client.V1PodSpec(
                                containers = [
                                    kubernetes.client.V1Container(
                                        name = siteid,
                                        image = "nginx:1.15",
                                        volume_mounts = [
                                            kubernetes.client.V1VolumeMount(
                                                name = "nginxconf",
                                                mount_path = "/etc/nginx"
                                            ),
                                            kubernetes.client.V1VolumeMount(
                                                name = "mimetypes",
                                                mount_path = "/etc/nginx/mime"
                                            )
                                        ]
                                    )
                                ],
                                volumes = [
                                    kubernetes.client.V1Volume(
                                        name = "nginxconf",
                                        config_map = kubernetes.client.V1ConfigMapVolumeSource(
                                            name = siteid
                                        )
                                    ),
                                    kubernetes.client.V1Volume(
                                        name = "mimetypes",
                                        config_map = kubernetes.client.V1ConfigMapVolumeSource(
                                            name = "mimetypes"
                                        )
                                    )
                                ]
                            )
                        )
                    )
                )
                api_response = self.apps_v1.create_namespaced_daemon_set(self.namespace, body)

                _logger.info(f"Creating nginx proxy service '{siteid}'...")
                body = kubernetes.client.V1Service(
                    metadata = kubernetes.client.V1ObjectMeta(name=siteid),
                    spec = kubernetes.client.V1ServiceSpec(
                        ports = [
                            kubernetes.client.V1ServicePort(
                                port = 8080,
                            )
                        ],
                        selector = {
                            "workload": f"proxy-{siteid}"
                        }
                    )
                )
                api_response = self.core_v1.create_namespaced_service(self.namespace, body)

                _logger.info(f"Creating nginx proxy ingress '{siteid}'...")
                rules = []
                for a in aliases + [hostname]:
                    rules.append(
                        #kubernetes.client.ExtensionsV1beta1IngressRule(
                        kubernetes.client.V1beta1IngressRule(
                            host = a,
                            # kubernetes>=10.0.0 - http = kubernetes.client.ExtensionsV1beta1HTTPIngressRuleValue(
                            http = kubernetes.client.V1beta1HTTPIngressRuleValue(
                                paths = [
                                    # kubernetes>=10.0.0 - kubernetes.client.ExtensionsV1beta1HTTPIngressPath(
                                    kubernetes.client.V1beta1HTTPIngressPath(
                                        #backend = kubernetes.client.ExtensionsV1beta1IngressBackend(
                                        backend = kubernetes.client.V1beta1IngressBackend(
                                            service_name = siteid,
                                            service_port = 8080
                                        ),
                                        path = "/"
                                    )
                                ]
                            )
                        )
                    )
                tls = [
                    # kubernetes>=10.0.0 - kubernetes.client.ExtensionsV1beta1IngressTLS(
                    kubernetes.client.V1beta1IngressTLS(
                        hosts = aliases + [hostname],
                        secret_name = f"{siteid}-le"
                    )
                ]
                #body = kubernetes.client.ExtensionsV1beta1Ingress(
                body = kubernetes.client.V1beta1Ingress(
                    metadata = kubernetes.client.V1ObjectMeta(name=siteid),
                    #spec = kubernetes.client.ExtensionsV1beta1IngressSpec(
                    spec = kubernetes.client.V1beta1IngressSpec(
                        #backend = kubernetes.client.ExtensionsV1beta1IngressBackend(
                        backend = kubernetes.client.V1beta1IngressBackend(
                            service_name = siteid,
                            service_port = 8080
                        ),
                        rules = rules,
                        tls = tls
                    )
                )
                api_response = self.ext_v1.create_namespaced_ingress(self.namespace, body)

        except Exception as e:
            _logger.exception(e)
            return str(e)

        return "OK"

    async def deploy_certificate(self, sitename, hostname, aliases):
        # This avoids situation where DNS for WAF not pointing to given hostname
        mainhostname = hostname
        if hostname not in aliases:
            mainhostname = aliases[0]

        siteid = sitename.split(".")[0]
        rawyaml = """
apiVersion: certmanager.k8s.io/v1alpha1
kind: Certificate
metadata:
  name: {{siteid}}-cert
  namespace: {{namespace}}
spec:
  acme:
    config:
    - dns01:
        provider: route53
      domains:
      - {{mainhostname}}
  commonName: {{mainhostname}}
  dnsNames:
  - {{mainhostname}}
  issuerRef:
    kind: ClusterIssuer
    name: letsencrypt-production
  secretName: {{siteid}}-tls
"""
        rawyaml = rawyaml.replace("{{siteid}}", siteid)
        rawyaml = rawyaml.replace("{{namespace}}", self.namespace)
        rawyaml = rawyaml.replace("{{mainhostname}}", mainhostname)
        model = yaml.load(rawyaml, Loader=yaml.SafeLoader)
        model['spec']['acme']['config'][0]['domains'] = aliases
        model['spec']['dnsNames'] = aliases

        path_params = {}
        auth_settings = ['BearerToken']
        header_params = {
            "Content-Type": "application/json"
        }
        query_params = []

        # Fetch latest state of resource to apply changes to
        response = self.api_client.call_api(f"/apis/certmanager.k8s.io/v1alpha1/namespaces/{self.namespace}/certificates", 'GET',
            path_params,
            query_params,
            header_params,
            auth_settings=auth_settings,
        )
        r = json.loads(self.api_client.last_response.data)
        certs = {x['metadata']['name']:x for x in r['items']}

        # If it doesn't exist, create it...
        certid = f"{siteid}-cert"
        try:
            if certid not in certs.keys():
                _logger.info(f"Creating certificate '{certid}' with {len(aliases)} hostnames...")
                response = self.api_client.call_api(f"/apis/certmanager.k8s.io/v1alpha1/namespaces/{self.namespace}/certificates", 'POST',
                    path_params,
                    query_params,
                    header_params,
                    body=model,
                    auth_settings=auth_settings,
                )
            else:
                _logger.info(f"Updating certificate '{certid}' with {len(aliases)} hostnames...")
                # Transplant metadata to allow update to work
                model['metadata'] = certs[certid]['metadata']

                # Attempt to update...
                response = self.api_client.call_api(f"/apis/certmanager.k8s.io/v1alpha1/namespaces/{self.namespace}/certificates/{certid}", 'PUT',
                    path_params,
                    query_params,
                    header_params,
                    body=model,
                    auth_settings=auth_settings,
                )
        except Exception as e:
            _logger.exception(e)
            return str(e)

        return "OK"

    async def fetch_ips_for_site(self, site):
        ingress = None
        siteid = site.label.split(".")[0]
        for i in self.ingresses:
            if siteid == i['metadata']['name']:
                ingress = i
                break
        if ingress is None:
            raise Exception(f"Could not find ingress {siteid} ({site.label})")
        return [x['ip'] for x in ingress['status']['loadBalancer']['ingress']]
