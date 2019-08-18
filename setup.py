from setuptools import setup

setup(name = 'site-domain-manager',
    version = '0.0.1',
    description = 'Minimal REST API service to manage mappings of sites, domains, DNS entries, WAFs, SSL certificates etc.',
    author = 'Ross Golder',
    author_email = 'rossg@golder.org',
    url = 'https://github.com/rossigee/site-domain-manager',
    packages = [
        'sdmgr',
        'sdmgr.auth',
        'sdmgr.waf',
        'sdmgr.waf.k8s',
        'sdmgr.registrar',
        'sdmgr.registrar.marcaria',
        'sdmgr.registrar.namecheap',
        'sdmgr.registrar.ionos',
        'sdmgr.registrar.uniteddomains',
        'sdmgr.dns_provider',
        'sdmgr.dns_provider.route53',
        'sdmgr.hosting',
        'sdmgr.hosting.cloudways',
        #'sdmgr.ssl',
    ],
    install_requires = [
        'gunicorn',
        'uvicorn',
        'starlette',
        'fastapi',
        'pyjwt',
        'databases',
        'orm',
        'boto3',
        'kubernetes',
        'aiohttp',
        'aiomysql',
        'aiosqlite',
        'aiodns',
        'python-multipart',
        'python-ldap',
        'mysqlclient',
    ],
    entry_points = {
        'console_scripts': [
            'sdmgr = sdmgr.app:main'
        ]
    })
