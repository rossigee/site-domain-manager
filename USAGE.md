# Introduction

This page explains some of the common processes involved in having this system manage domains for a given site.

To make the curl examples more useful, they use a `$SDMGR_URL` envvar which can be set according to your needs. For example:

```bash
export SDMGR_URL=http://localhost:8000  # for local development
# or...
export SDMGR_URL=https://sdmgr.yourdomain.com # for a more permanent service
```

## Main endpoints

Typically the URI parts will be made up of collection, id and action parts as required.

| Collection | Action | URI |
|--------|--------|-----|
| Sites | List | GET /sites |
| Sites | Create | POST /sites |
| Sites | Update | POST /sites/<i>id</i> |
| Sites | Delete | DELETE /sites/<i>id</i> |
| Sites | Run checks | GET /sites/<i>id</i>/check |
| Domain | List | GET /domains |
| Domain | Create | POST /domains |
| Domain | Update | POST /domains/<i>id</i> |
| Domain | Delete | DELETE /domains/<i>id</i> |
| Registrars | List | GET /registrars |


## List filters

...

# Listing sites

Sites can be listed with the API call:

```
curl -sk -utesting:onetwothree $SDMGR_URL/sites
```


# Creating sites

Sites should be created manually on the hosting provider first, and labelled accordingly.

For Cloudways, ensure the site's label is set to the main hostname for the site.

Then, issue a 'refresh' API call on the hosting provider's agent:

```
curl -sk -utesting:onetwothree $SDMGR_URL/hosting/1/refresh
```

This will re-import and update any site records.

# Creating domains

Domains just need to be registered with one of the supported/configured registrars.

## Marcaria

For Marcaria, register the domain and download a fresh list of domains (i.e. `Export_Domain_Lists.csv`). Upload the domains with the 'csvfile' API call on the Marcaria registrar endpoint.

```
curl -sk -utesting:onetwothree -X POST -Fcsvfile=@Export_Domain_Lists.csv $SDMGR_URL/registrars/1/csvfile
```

## Namecheap

For Namecheap, just register the domain on Namecheap then update the list of domains via the 'refresh' API call.

In both cases, the 'domains' objects should now exist.

Domains can be listed with the 'list' API call:

```
curl -sk -utesting:onetwothree $SDMGR_URL/domains
```

# Performing checks

For now, the individual checks can be called via the domain endpoints.

## Registrar status for a domain

To check a specific registrar handler for information about a domain.

```
curl -sk -utesting:onetwothree $SDMGR_URL/registrars/1/domains/swanson.co.nz/status
```

## NS records

To check that we have a Route53 zone created and that the NS records are correctly set on the domain, you can use the 'check NS records' API call:

```
curl -sk -utesting:onetwothree $SDMGR_URL/domains/31/check/ns
```

This will check public DNS servers for the 'NS' records, and generate a request to the registrar if the NS records need setting/resetting. It will also create a Route53 zone for the domain if one does not already exist.


## A records

To check that the A records on the domain are correctly set to point to your site (via WAF where applicable), you can use the 'check A records' API call:

```
curl -sk -utesting:onetwothree $SDMGR_URL/domains/31/check/a
```

This will points the domain to the IP address of the domain's WAF. If no WAF is specified, it will point the domain to the IP address of the site host directly.


# Other stuff


Fetch API schema mapping:

```
curl -sk -utesting:onetwothree $SDMGR_URL/schema
```

Updating the Route53 domain list...

```
curl -utesting:onetwothree -k $SDMGR_URL/dns/1/refesh
