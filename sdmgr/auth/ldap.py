from fastapi import HTTPException

import ldap, os
import json

async def auth(username, password):
    authconfig_filename = os.getenv("AUTH_CONFIG")
    authconfig = json.load(authconfig_filename)

    ldap_url = authconfig['ldap_url']
    connect = ldap.initialize(ldap_url)
    connect.set_option(ldap.OPT_REFERRALS, 0)

    # Bind as search user (find DN to auth user with)
    bind_dn = authconfig['ldap_bind_dn']
    bind_pw = authconfig['ldap_bind_pw']
    base_dn = authconfig['ldap_search_dn']
    user_search_filter = authconfig['ldap_filter'] % { 'username': username }
    try:
        connect.simple_bind_s(bind_dn, bind_pw)
    except ldap.LDAPError as e:
        raise HTTPException(status_code=400, detail=f"LDAP bind error: {str(e)}")

    try:
        results = connect.search_s(base_dn, ldap.SCOPE_SUBTREE, user_search_filter, ['objectclass'], 1)
        if len(results) != 1:
            raise HTTPException(status_code=400, detail=f"LDAP user search error: {len(results)} users found.")

        user_entry = results[0]
        ldap_dn = user_entry[0]
        if ldap_dn == None:
            raise HTTPException(status_code=400, detail=f"LDAP user search error: Matched object has no DN.")

        # TODO: Check group membership (here or below?)
    except ldap.LDAPError as e:
        raise HTTPException(status_code=400, detail=f"LDAP user search error: {str(e)}")

    # Bind as user (check authentication)
    try:
        connect.simple_bind_s(ldap_dn, password)
    except ldap.LDAPError as e:
        raise HTTPException(status_code=400, detail=f"LDAP bind error: {str(e)}")

    # Tidy up
    connect.unbind_s()
