from typing import List

import requests

from models.config import RadarrConfig


class RadarrService:
    def __init__(self, config: RadarrConfig):
        self.config = config

        self.session = requests.Session()
        self.session.params = {"apikey": self.config.api_key}

    def get_movies(self) -> List[dict]:
        response = self.session.get(f"{self.config.url}/api/v3/movie")
        response.raise_for_status()
        return response.json()

    def delete_movie(self, movie_id: int, delete_files: bool = True) -> bool:
        response = self.session.delete(
            f"{self.config.url}/api/v3/movie/{movie_id}",
            params={"deleteFiles": delete_files},
        )

        return response.status_code == 200
