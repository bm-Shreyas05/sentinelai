"""Alert dispatch: console log (always), SMTP email and JSON webhook (e.g. Slack) when configured."""
import json, logging, smtplib, time
from email.message import EmailMessage

import httpx

log = logging.getLogger("sentinelai.alerts")


class Dispatcher:
    def __init__(self, settings, conn):
        self.s, self.conn = settings, conn

    def send(self, txn_id, audience, subject, body):
        channels = ["console"]
        log.warning("[ALERT → %s] %s | %s", audience, subject, body)
        if audience == "analyst" and self.s.smtp_host and self.s.alert_email_to:
            channels.append(self._email(subject, body))
        if self.s.alert_webhook_url:
            channels.append(self._webhook(audience, subject, body))
        status = ",".join(channels)
        self.conn.execute("INSERT INTO alerts(txn_id, audience, channel, status, body, created_at) "
                          "VALUES (?,?,?,?,?,?)", (txn_id, audience, status, "sent", body, time.time()))
        self.conn.commit()
        return status

    def _email(self, subject, body):
        try:
            msg = EmailMessage()
            msg["Subject"], msg["From"], msg["To"] = subject, self.s.smtp_user, self.s.alert_email_to
            msg.set_content(body)
            with smtplib.SMTP(self.s.smtp_host, self.s.smtp_port, timeout=10) as smtp:
                smtp.starttls(); smtp.login(self.s.smtp_user, self.s.smtp_password); smtp.send_message(msg)
            return "email"
        except Exception as exc:   # never let a notification failure break scoring
            log.error("email failed: %s", exc); return "email_failed"

    def _webhook(self, audience, subject, body):
        try:
            httpx.post(self.s.alert_webhook_url, timeout=5,
                       json={"text": f"*{subject}* ({audience})\n{body}"}).raise_for_status()
            return "webhook"
        except Exception as exc:
            log.error("webhook failed: %s", exc); return "webhook_failed"
