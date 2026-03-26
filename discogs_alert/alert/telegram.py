import json
import logging
from pathlib import Path
from typing import Optional

import requests

from discogs_alert.alert.base import AlertDict, Alerter

logger = logging.getLogger(__name__)


class TelegramAlerter(Alerter):
    def __init__(self, telegram_token: str, telegram_chat_id: str, alert_state_path: Optional[str] = None):
        self.bot_token = telegram_token
        self.bot_chat_id = telegram_chat_id
        self.state_path = Path(alert_state_path) if alert_state_path else None

    def get_all_alerts(self) -> AlertDict:
        if self.state_path is None or not self.state_path.exists():
            return {}
        try:
            raw = json.loads(self.state_path.read_text())
            return {title: set(bodies) for title, bodies in raw.items()}
        except (json.JSONDecodeError, OSError):
            logger.warning("Failed to read alert state file, starting fresh", exc_info=True)
            return {}

    def send_alert(self, message_title: str, message_body: str):
        resp = requests.get(
            "https://api.telegram.org/bot"
            + self.bot_token
            + "/sendMessage?chat_id="
            + self.bot_chat_id
            + "&parse_mode=Markdown&text="
            + message_title
            + f" ({message_body})"
        )
        if resp.ok:
            self._persist_alert(message_title, message_body)
        else:
            logger.error(f"Telegram send failed (status {resp.status_code}): {resp.text}")

    def _persist_alert(self, message_title: str, message_body: str):
        if self.state_path is None:
            return
        alerts = self.get_all_alerts()
        if message_title not in alerts:
            alerts[message_title] = set()
        alerts[message_title].add(message_body)

        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        serializable = {title: sorted(bodies) for title, bodies in alerts.items()}
        self.state_path.write_text(json.dumps(serializable, indent=2))
