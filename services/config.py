import os
from pathlib import Path

import yaml
from dotenv import load_dotenv

from models.config import (
    AuditConfig,
    Config,
    DaysThreshold,
    NtfyConfig,
    OverseerrConfig,
    PlexConfig,
    RadarrConfig,
    RatingThreshold,
    TautulliConfig,
)


class ConfigManager:
    def __init__(self, config_path: str = "config.yaml"):
        self.config_path = Path(config_path)

        # Load .env
        load_dotenv()

        # Load config.yaml
        self.config = self._load_config()

    def _find_arr_instances(self) -> tuple[str]:
        """
        Find configured Radarr and Sonarr instances from environment variables.

        Scans environment variables for any that start with 'radarr' or 'sonarr'.
        For variables with instance-specific names (e.g. radarr_4k_url), extracts
        the instance identifier (e.g. 'radarr_4k') and adds it to the set of instances.

        The method looks at the structure of the environment variable names:
        - Basic vars like RADARR_URL are treated as the default instance
        - Instance-specific vars like RADARR_4K_URL create instance names like 'radarr_4k'
        - Special suffixes 'url', 'api', and 'instances' are ignored for instance naming

        Returns:
            tuple[str]: Tuple of unique Radarr/Sonarr instance identifiers found in
                       environment variables (e.g. ('radarr_4k', 'radarr_1080p', 'sonarr'))
        """

        # Get all environment variables starting with radarr or sonarr
        arr_instances = set()
        for key in os.environ:
            if key.lower().startswith(("radarr", "sonarr")):
                # Split the env var name into parts
                parts = key.lower().split("_")

                if len(parts) >= 2:
                    # If it has a specific instance (e.g. radarr_4k_url)
                    if parts[1] not in ("url", "api", "instances"):
                        parts[0] = f"{parts[0]}_{parts[1]}"

                arr_instances.add(parts[0])

        return tuple(arr_instances)

    def _load_config(self) -> Config:
        """
        Load and parse configuration from config.yaml and environment variables.

        This method reads the config.yaml file and merges it with environment variables.
        Environment variables take precedence over config file values.

        The following configurations are loaded:
        - Plex server details (URL and token)
        - Tautulli details (URL and API key)
        - Multiple Radarr/Sonarr instances (URLs and API keys)
          Instances are auto-detected from environment variables
        - Overseerr details (URL, API key, email, password, admin emails)
        - Deletion thresholds:
          - Days threshold for admin users, regular users, and low-rated content
          - Rating threshold for admin users, regular users, and low-rated content

        Environment variables should follow the pattern:
        - Basic: SERVICE_FIELD (e.g. PLEX_URL)
        - Instance-specific: SERVICE_INSTANCE_FIELD (e.g. RADARR_4K_URL)

        Returns:
            Config: A Config object containing all parsed configuration values
        """

        with open(self.config_path) as f:
            data = yaml.safe_load(f)

            fields = {
                "plex": ["url", "token"],
                "tautulli": ["url", "api_key"],
                "overseerr": ["url", "api_key", "email", "password", "admin_emails"],
            }

            for arr_instance in self._find_arr_instances():
                fields[arr_instance] = ["url", "api_key"]

            for key in fields.keys():
                for field in fields[key]:
                    if var := os.environ.get(f"{key.upper()}_{field.upper()}"):
                        data.setdefault(key, {})
                        data[key][field] = var

        return Config(
            plex=PlexConfig(
                url=data["plex"]["url"],
                token=data["plex"]["token"],
            ),
            tautulli=TautulliConfig(
                url=data["tautulli"]["url"],
                api_key=data["tautulli"]["api_key"],
            ),
            radarr=[
                RadarrConfig(
                    url=data[instance]["url"],
                    api_key=data[instance]["api_key"],
                    name=instance,
                )
                for instance in data
                if "radarr" in instance
            ],
            overseerr=OverseerrConfig(
                url=data["overseerr"]["url"],
                api_key=data["overseerr"]["api_key"],
                email=data["overseerr"]["email"],
                password=data["overseerr"]["password"],
                admin_emails=data["overseerr"]["admin_emails"],
            ),
            days_threshold=DaysThreshold(
                admin=data["deletion_threshold"]["days"]["users"]["admin"],
                user=data["deletion_threshold"]["days"]["users"]["user"],
                low_rating=data["deletion_threshold"]["days"]["rules"]["low_rated"],
                mid=data["deletion_threshold"]["days"]["rules"].get("mid", 90),
            ),
            rating_threshold=RatingThreshold(
                admin=data["deletion_threshold"]["rating"]["users"]["admin"],
                user=data["deletion_threshold"]["rating"]["users"]["user"],
                low_rating=data["deletion_threshold"]["rating"]["rules"]["low"],
                imdb_protect=data["deletion_threshold"]["rating"]["rules"].get(
                    "imdb_protect", 8.0
                ),
            ),
            audit=AuditConfig(
                log_path=data.get("audit", {}).get(
                    "log_path", "output/deletions.jsonl"
                ),
                summary_path=data.get("audit", {}).get(
                    "summary_path", "output/expiring_soon.txt"
                ),
                expiring_soon_days=data.get("audit", {}).get("expiring_soon_days", 30),
            ),
            ntfy=self._load_ntfy(data.get("ntfy", {})),
        )

    def _load_ntfy(self, data: dict) -> NtfyConfig:
        """Build the ntfy config, letting NTFY_* env vars override the file."""
        return NtfyConfig(
            enabled=data.get("enabled", False),
            server=os.environ.get("NTFY_SERVER", data.get("server", "https://ntfy.sh")),
            topic=os.environ.get("NTFY_TOPIC", data.get("topic", "")),
            priority=data.get("priority", "default"),
            notify_within_days=data.get("notify_within_days", 1),
        )
