from typing import List

import requests

from models.config import RadarrConfig


class RadarrService:
    def __init__(self, config: RadarrConfig):
        self.config = config

    def get_movies(self) -> List[dict]:
        response = requests.get(
            f"{self.config.url}/api/v3/movie", params={"apikey": self.config.api_key}
        )
        response.raise_for_status()
        return response.json()

    def delete_movie(self, movie_id: int, delete_files: bool = True) -> bool:
        response = requests.delete(
            f"{self.config.url}/api/v3/movie/{movie_id}",
            params={"apikey": self.config.api_key, "deleteFiles": delete_files},
        )

        return response.status_code == 200
