from starlette.config import Config
from starlette.datastructures import URL, Secret

config = Config(".env")

DEBUG = config('DEBUG', cast=bool, default=False)
TESTING = config('TESTING', cast=bool, default=False)
#SECRET_KEY = config('SECRET_KEY', cast=Secret)

DATABASE_URL = config('DATABASE_URL', cast=URL)
if TESTING:
    DATABASE_URL = DATABASE_URL.replace(database='test_' + DATABASE_URL.database)

# Modules to import (and register) agents from
agents_to_import = [
    #"sdmgr.hosting",
    "sdmgr.registrar.marcaria",
    "sdmgr.registrar.uniteddomains",
    "sdmgr.registrar.namecheap",
    "sdmgr.registrar.ionos",
    "sdmgr.waf.k8s",
    #"sdmgr.waf.cloudflare",
    "sdmgr.dns_provider.route53",
    #"sdmgr.dns_provider.cloudflare",
    "sdmgr.notifiers.discord",
    "sdmgr.notifiers.smtp",
]
