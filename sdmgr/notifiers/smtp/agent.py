from ..base import NotifierAgent

import logging
_logger = logging.getLogger(__name__)

import os
from email.mime.text import MIMEText
import aiosmtplib


class SMTP(NotifierAgent):
    _label_ = "SMTP"

    _settings_ = [
        {
            'key': "smtp_host",
            'description': "SMTP host",
        },
        {
            'key': "smtp_port",
            'description': "SMTP port",
        },
        {
            'key': "smtp_user",
            'description': "SMTP username",
        },
        {
            'key': "smtp_pass",
            'description': "SMTP password",
        },
        {
            'key': "smtp_use_tls",
            'description': "SMTP use TLS",
        },
        {
            'key': "smtp_starttls",
            'description': "SMTP STARTTLS",
        },
        {
            'key': "mail_from_label",
            'description': "Name or label for mail from address",
        },
        {
            'key': "mail_from_address",
            'description': "E-mail address for mail from address",
        },
        {
            'key': "mail_to_label",
            'description': "Name or label for mail to address",
        },
        {
            'key': "mail_to_address",
            'description': "E-mail address for mail to address",
        },
    ]

    def __init__(self, data):
        _logger.info(f"Loading SMTP notifier agent (id: {data.id}): {data.label})")
        NotifierAgent.__init__(self, data)

    async def notify_registrar_ns_update(self, registrar, domain, nameservers):
        subject = f"NS record update required for '{domain.name}'"

        content = f"Please update NS records for domain '{domain.name}' to:\n"
        content += ("\n".join(nameservers))

        await self._send(subject, content)

    async def _send(self, subject, content):
        smtp_host = self._config("smtp_host")
        smtp_port = intval(self._config("smtp_port"))
        smtp_user = self._config("smtp_user")
        smtp_pass = self._config("smtp_pass")
        smtp_use_tls = self._config("smtp_user_tls") > 0
        smtp_starttls = self._config("smtp_starttls") > 0
        mail_from_label = self._config("mail_from_label")
        mail_from_address = self._config("mail_from_address")
        mail_to_label = self._config("mail_to_label")
        mail_to_address = self._config("mail_to_address")

        message = MIMEText(content)
        message["From"] = f"{mail_from_label} <{mail_from_address}>"
        message["To"] = f"{mail_to_label} <{mail_to_address}>"
        message["Subject"] = subject

        try:
            output = await aiosmtplib.send(message,
                hostname=smtp_host,
                port=smtp_port,
                username=smtp_user,
                password=smtp_pass,
                use_tls=smtp_use_tls,
                starttls=smtp_starttls
            )
            print(output)

        except Exception as e:
            _logger.exception(e)
