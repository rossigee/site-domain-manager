# Hopefully just temporary. Should use something more robust, such as OAuth2.

from starlette.authentication import (
    AuthenticationBackend, AuthenticationError, SimpleUser, UnauthenticatedUser,
    AuthCredentials
)
from starlette.responses import JSONResponse

import base64
import binascii


class BasicAuthBackend(AuthenticationBackend):
    async def authenticate(self, request):
        if "Authorization" not in request.headers:
            return

        auth = request.headers["Authorization"]
        try:
            scheme, credentials = auth.split()
            if scheme.lower() != 'basic':
                return
            decoded = base64.b64decode(credentials).decode("ascii")
        except (ValueError, UnicodeDecodeError, binascii.Error) as exc:
            raise AuthenticationError('Invalid basic auth credentials')

        username, _, password = decoded.partition(":")

        # IMPORTANT: Checking of the auth token against a backend (i.e. LDAP)
        # should occur before the request hits the app. The extraction and use
        # of the username here is simply for auditting purposes...
        creds = []
        if username != "":
            creds = ["authenticated"]
        return AuthCredentials(creds), SimpleUser(username)


class UnauthenticatedResponse(JSONResponse):
    def __init__(self):
        headers = {
            "WWW-Authenticate": "Basic realm=SiteDomainManager"
        }
        super(UnauthenticatedResponse, self).__init__({"error": "unauthenticated"}, status_code=401, headers=headers)
