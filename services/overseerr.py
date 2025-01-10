from typing import List

import requests

from models.config import OverseerrConfig


class OverseerrService:
    def __init__(self, overseerr_config: OverseerrConfig):
        self.config = overseerr_config

        # Set up session
        self.session = requests.Session()
        self._authenticate()

    def _authenticate(self) -> None:
        url = f"{self.config.url}/api/v1/auth/local"
        response = self.session.post(
            url,
            headers=self._get_headers(),
            json={"email": self.config.email, "password": self.config.password},
        )
        response.raise_for_status()

    def _get_headers(self) -> dict:
        return {"X-Api-Key": self.config.api_key}

    def get_all_requests(self) -> List[any]:
        all_requests = []
        for page in range(1, 10):
            url = f"{self.config.url}/api/v1/request"
            params = {"take": 250, "skip": (page - 1) * 250, "sort": "added", "filter": "available"}
            response = self.session.get(url, headers=self._get_headers(), params=params)
            response.raise_for_status()
            data = response.json()
            all_requests.extend(data["results"])
        return all_requests

    def _is_admin_request(self, request: dict) -> bool:
        return request["requestedBy"]["email"] in self.config.admin_emails
