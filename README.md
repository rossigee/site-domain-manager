# Site Domain Manager

This package provides a service that aims to (semi-)automate the management of our extensive portfolio of domain names, spread across several registrars, and ensure that are pointing to the correct nameservers, that the nameservers have entries pointing to the correct site, and that the site is correctly configured/provisioned to respond to requests for the expected hostnames, and will present valid SSL certificates when users connect to them via their respective WAF/proxy endpoints.

It is agnostic of the applications being served, which means it can be used to manage the mappings of domains to sites across an organisation.

Details about the sites and their respective domains are added via API calls, or via the admin interface. The service recognises when domains are added/updated and performs the necessary actions to make it reached the desired state of hosting.

A background task will constantly monitor the state of these domains and use a designated notification channel (i.e. an e-mail address, or an IM channel) to provide humans with information they need to do manually tasks that cannot or are not yet automated (i.e. updates of NS records with some registrars), or to alert them to the failure of an automation action, or other inconsistent state.

## Design

It is designed to run as a typical background service, managed via a simple REST API. It may be that we manage the main models in an external system (i.e. WordPress CMS), and have a WordPress plugin feed adds/updates of the state of those models into this service via API calls.

Later, to simplify troubleshooting/management, a simple interface may be provided either in the form of traditional web UI using a simple Bootstrap/similar SPA, and/or maybe in the form of a CLI style interface using an instant messaging (Discord) chat bot, which will respond interactively to commands to list, update and check domains.

The 'app' itself provides basic CRUD abilities for a small set of objects. There is a 'manager' object that responds to certain types of request, and uses the data in the objects available to carry out the request. Often the request may take minutes/hours to complete, so the API has been designed to be asynchronous.

TODO: There will be a 'schedule' thread, which will periodically select domains to be checked, run the necessary checks/fixes on them, and report any anomalies via the notification channel.

There are agents to interact with the various third party entiries involved in each hosting arrangement. The main agents are:

* Registrar agents - Who we register the domains with. We have several registrars, due to the international range of our domain acquisitions. I have attempted to handle Marcaria, Namecheap and IONOS. The agents allow us to reset the NS records for the domain and update the registrant and billing details for the domain.
* DNS provider agents - Essentially, this is Route53, although it should be easy enough to add support for Azure or any other suitable API-based DNS service. The agent allows us to query and update the domain's DNS records.
* WAF provider agents - These agents manage Load Balancers, Reverse Proxies, CDNs and/or WAF layers. Basically, anything that goes 'in front' of the app hosting servers themselves, and intercept/filter traffic directed at them. Additionally, they will act as the SSL termination point, so will need to be provisioned with Digicert (EV SSL) certificates for some domains, and will need to be able to manage LetsEncrypt certificates for all remaining domains.
* Hosting provider agents - These agents simply keep the app servers informed about which domains should be directed to which of their sites, as well as retrieve the IP address(es) of the app servers that need to be configured via the WAF provider, so the WAF layer knows where to proxy inbound web requests.

The main database models that the above agents work with are:

* Site - This represents a site running a web application, and provides details of which hosting provider it's running on, and can be used to obtain the site's main back-end app service IP addresses.
* Domain - There are multiple domains per site. Each domain provides details of which registrar, DNS provider and WAF provider to interact with to have the domain point to the site.

Once added to the service, an async process is started for each site and domain that periodically assesses it's status. Essentially, it performs various checks to endure that the desired state in the provided config file matches the real world state as found by making checks (via direct API calls where possible) with the provider of the resource (domain registration, DNS hosting, SSL certificate, analytics provisioning, monitoring/alerting updates etc.) in question.


## Development notes

To push a new build and make it active...

```
docker build . -t agentwordpressregistry1.azurecr.io/sdmgr && \
  docker push agentwordpressregistry1.azurecr.io/sdmgr && \
  kubectl delete pod -l purpose=SiteDomainManager
```

Very quick 'getting started' for local use...

```
virtualenv -p python3 /tmp/sdmgr-env
python setup.py sdist
pip3 install dist/site-domain-manager-0.0.1.tar.gz
pip3 install aiosqlite
export DATABASE_URL=sqlite:///db.sqlite
sdmgr
```
