"""
weblance_project/brevo_backend.py
──────────────────────────────────
Custom Django email backend:
  Primary  → Brevo REST API (HTTPS port 443, no SMTP port issues on Render)
  Fallback → Gmail SMTP (when Brevo returns 401 IP-blocked)

Settings required:
    BREVO_API_KEY   = 'xkeysib-...'   (set in Render env vars)
    EMAIL_HOST_USER = 'infoweblance01@gmail.com'
    EMAIL_HOST_PASSWORD = '<gmail app password>'
"""

import json
import logging
import smtplib
import ssl
import urllib.request
import urllib.error
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import base64

from django.core.mail.backends.base import BaseEmailBackend
from django.conf import settings

logger = logging.getLogger(__name__)

BREVO_API_URL = 'https://api.brevo.com/v3/smtp/email'


class BrevoAPIBackend(BaseEmailBackend):
    """
    Sends via Brevo REST API with automatic Gmail SMTP fallback.
    """

    def open(self):
        return True

    def close(self):
        pass

    def send_messages(self, email_messages):
        if not email_messages:
            return 0
        sent = 0
        for msg in email_messages:
            try:
                if self._send(msg):
                    sent += 1
            except Exception as exc:
                logger.error('EmailBackend: send failed — %s', exc)
                if not self.fail_silently:
                    raise
        return sent

    # ──────────────────────────────────────────────────────────────
    # PRIMARY: Brevo REST API
    # ──────────────────────────────────────────────────────────────
    def _send(self, msg):
        api_key = getattr(settings, 'BREVO_API_KEY', '').strip()

        # Skip Brevo if no API key — go straight to Gmail
        if not api_key:
            logger.info('BREVO_API_KEY not set — using Gmail directly')
            return self._gmail_fallback(msg)

        # Try Brevo first, fall back to Gmail on any failure
        try:
            return self._brevo_send(msg, api_key)
        except Exception as e:
            logger.warning('Brevo failed (%s) — trying Gmail fallback', e)
            return self._gmail_fallback(msg)

    def _brevo_send(self, msg, api_key):

        to_list = [{'email': addr} for addr in (msg.to or [])]
        if not to_list:
            return False

        from_email = msg.from_email or getattr(settings, 'DEFAULT_FROM_EMAIL', '')
        if '<' in from_email and '>' in from_email:
            name_part, addr_part = from_email.split('<', 1)
            sender = {
                'name':  name_part.strip().strip('"'),
                'email': addr_part.strip().rstrip('>'),
            }
        else:
            sender = {'name': 'Weblance', 'email': from_email.strip()}

        html_body  = None
        plain_body = msg.body or ''
        if hasattr(msg, 'alternatives'):
            for content, mimetype in msg.alternatives:
                if mimetype == 'text/html':
                    html_body = content
                    break

        payload = {
            'sender':      sender,
            'to':          to_list,
            'subject':     msg.subject or '(no subject)',
            'textContent': plain_body,
        }
        if html_body:
            payload['htmlContent'] = html_body
        if msg.cc:
            payload['cc']  = [{'email': a} for a in msg.cc]
        if msg.bcc:
            payload['bcc'] = [{'email': a} for a in msg.bcc]

        if msg.attachments:
            attachments = []
            for att in msg.attachments:
                if isinstance(att, MIMEBase):
                    content = att.get_payload(decode=True)
                    name    = att.get_filename() or 'attachment'
                elif isinstance(att, tuple) and len(att) >= 2:
                    name, content = att[0], att[1]
                    if isinstance(content, str):
                        content = content.encode()
                else:
                    continue
                attachments.append({
                    'name':    name,
                    'content': base64.b64encode(content).decode(),
                })
            if attachments:
                payload['attachment'] = attachments

        data = json.dumps(payload).encode('utf-8')
        req  = urllib.request.Request(
            BREVO_API_URL,
            data=data,
            headers={
                'accept':       'application/json',
                'api-key':      api_key,
                'content-type': 'application/json',
            },
            method='POST',
        )

        try:
            resp   = urllib.request.urlopen(req, timeout=10)  # longer timeout for Render
            result = json.loads(resp.read().decode())
            logger.info('Brevo API: sent to %s — messageId=%s',
                        [a['email'] for a in to_list],
                        result.get('messageId', '?'))
            return True

        except urllib.error.HTTPError as e:
            body = e.read().decode()
            logger.error('Brevo API: HTTP %s — %s', e.code, body)
            # Always fall back to Gmail on any Brevo error
            logger.warning('Brevo blocked (HTTP %s) — trying Gmail fallback', e.code)
            return self._gmail_fallback(msg)

        except Exception as e:
            logger.error('Brevo API: connection error — %s', e)
            logger.warning('Brevo failed — trying Gmail fallback')
            return self._gmail_fallback(msg)

    # ──────────────────────────────────────────────────────────────
    # FALLBACK: Gmail SMTP (SSL port 465)
    # ──────────────────────────────────────────────────────────────
    def _gmail_fallback(self, msg):
        """Send via Gmail SMTP SSL as fallback when Brevo is unavailable."""
        user     = getattr(settings, 'EMAIL_HOST_USER', '').strip()
        password = getattr(settings, 'EMAIL_HOST_PASSWORD', '').strip()

        if not user or not password:
            logger.error('Gmail fallback: EMAIL_HOST_USER / EMAIL_HOST_PASSWORD not set')
            raise RuntimeError('Gmail fallback: credentials not configured')

        to_addrs = list(msg.to or [])
        if not to_addrs:
            return False

        # Build MIME message
        mime = MIMEMultipart('alternative')
        mime['Subject'] = msg.subject or '(no subject)'
        mime['From']    = msg.from_email or getattr(settings, 'DEFAULT_FROM_EMAIL', user)
        mime['To']      = ', '.join(to_addrs)
        if msg.cc:
            mime['Cc'] = ', '.join(msg.cc)

        # Plain text part
        if msg.body:
            mime.attach(MIMEText(msg.body, 'plain', 'utf-8'))

        # HTML part
        if hasattr(msg, 'alternatives'):
            for content, mimetype in msg.alternatives:
                if mimetype == 'text/html':
                    mime.attach(MIMEText(content, 'html', 'utf-8'))
                    break

        # Attachments
        if msg.attachments:
            from email.mime.application import MIMEApplication
            for att in msg.attachments:
                if isinstance(att, tuple) and len(att) >= 2:
                    name, content = att[0], att[1]
                    if isinstance(content, str):
                        content = content.encode()
                    part = MIMEApplication(content, Name=name)
                    part['Content-Disposition'] = f'attachment; filename="{name}"'
                    mime.attach(part)

        all_recipients = to_addrs + list(msg.cc or []) + list(msg.bcc or [])

        try:
            ctx = ssl.create_default_context()
            with smtplib.SMTP_SSL('smtp.gmail.com', 465, context=ctx, timeout=15) as server:
                server.login(user, password)
                server.sendmail(user, all_recipients, mime.as_string())
            logger.info('Gmail fallback: sent to %s', all_recipients)
            return True
        except Exception as exc:
            logger.error('Gmail fallback: failed — %s', exc)
            raise RuntimeError(f'Gmail fallback failed: {exc}')
