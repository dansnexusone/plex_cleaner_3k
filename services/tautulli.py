from datetime import datetime
from typing import Optional

import requests


class TautulliService:
    def __init__(self, config):
        self.base_url = config.tautulli_url
        self.api_key = config.tautulli_api_key

    def get_last_watched(self, rating_key: str) -> Optional[datetime]:
        """Get the last watched date for any user for the given rating key."""
        params = {
            "apikey": self.api_key,
            "cmd": "get_history",
            "rating_key": rating_key,
            "length": 1,
        }

        try:
            response = requests.get(f"{self.base_url}/api/v2", params=params)
            response.raise_for_status()
            data = response.json()

            if data["response"]["result"] == "success" and data["response"]["data"]["data"]:
                last_watched_ts = data["response"]["data"]["data"][0]["date"]
                return datetime.fromtimestamp(last_watched_ts)
            return None
        except Exception:
            return None
