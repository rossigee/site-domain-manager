# Authentication

The API is authenticated via OAuth2 'password' method. The actual backend used for authentication is configurable. The endpoint to authenticate to is:

`/api/v1/token`

This is configured via the following environment variables:

| Envvar | Value | Default | Example |
|--------|-------|---------|---------|
| AUTH_MODULE | Python3 module to import | `sdmgr.auth.test` | `sdmgr.auth.ldap` |

There is planned support for making authentication more configurable (i.e. Webauthn), but for now, the LDAP service is the only supported service.


## Test authentication

This is just a simple auth module for local development and testing purposes only. It simply accepts the following credentials:

| Role | Username | Password |
|------|----------|----------|
| Manager | `manager` | `bigboss` |
| Administrator | `admin` | `caretaker` |


## LDAP authentication

This is configured via environment variables:

| Envvar | Value | Example |
|--------|-------|---------|
| LDAP_URL | URL to connect to | `ldaps://ldap.yourdomain.com:636` |
| LDAP_BIND_DN | Bind DN for connection | `cn=User1,cn=Users,dc=yourdomain,dc=com` |
| LDAP_BIND_PW | Bind password for connection | `secretpassword` |
| LDAP_FILTER | Search filter for fetching user | `(sAMAccountName=%(username)s)` |
| LDAP_SEARCH_DN | Base DN for search | `cn=Users,dc=yourdomain,dc=com` |
