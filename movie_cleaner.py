import functools
import html
import json
import logging
from concurrent.futures import ThreadPoolExecutor
from dataclasses import fields
from datetime import datetime, timedelta
from typing import List, Optional

import requests
import urllib3
from bs4 import BeautifulSoup
from plexapi.exceptions import NotFound
from plexapi.server import PlexServer
from tqdm import tqdm

from models.external_rating import ExternalRating
from models.movie_info import MovieInfo
from services.config import ConfigManager
from services.overseerr import OverseerrService
from services.radarr import RadarrService
from services.tautulli import TautulliService

logger = logging.getLogger(__name__)

# Disable SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class MovieCleaner:
    """Manages the cleanup of movies from Radarr and Plex based on watch history and ratings."""

    def __init__(self):
        """Initialize MovieCleaner with necessary service connections."""
        self.config = ConfigManager().config
        self.overseerr = OverseerrService(self.config)
        self.radarr_uhd = RadarrService(self.config.radarr_uhd)
        self.radarr_streaming = RadarrService(self.config.radarr_streaming)
        self.plex = PlexServer(self.config.plex_url, self.config.plex_token)
        self.tautulli = TautulliService(self.config)

        self.overseerr_requests = self.overseerr.get_all_requests()
        self.imdb_top_250 = self.scrape_imdb_top_250()

        self.combined_movies = self.get_combined_movies()
        self.upcoming_movies = []

    def get_combined_movies(self) -> dict[str, list[dict]]:
        """Get combined movie data from both UHD and HD Radarr instances.

        This method fetches movies from both UHD and HD Radarr instances and combines them
        into a single dictionary keyed by TMDB ID. Only movies that have associated files
        are included.

        Returns:
            dict[str, list[dict]]: A dictionary where:
                - key (str): TMDB ID of the movie
                - value (list[dict]): List of movie dictionaries containing movie data from Radarr,
                                     with an additional 'type' field indicating 'uhd' or 'hd'

        Example structure:
            {
                "12345": [
                    {"type": "uhd", "tmdbId": 12345, ...},
                    {"type": "hd", "tmdbId": 12345, ...}
                ]
            }
        """
        combined_movies = {}
        for radarr_type, function in zip(
            ["uhd", "hd"], [self.radarr_uhd.get_movies, self.radarr_streaming.get_movies]
        ):
            movies = function()
            for movie in movies:
                if not movie["hasFile"]:
                    continue

                movie = {"type": radarr_type, **movie}

                tmdbid = str(movie["tmdbId"])
                if tmdbid not in combined_movies:
                    combined_movies[tmdbid] = [movie]
                else:
                    combined_movies[tmdbid].append(movie)

        return combined_movies

    def get_external_ratings(self, radarr_movie: dict) -> ExternalRating:
        """Get external ratings for a movie from TMDB."""
        ratings = {
            "imdb": None,
            "rotten_tomatoes": None,
            "tmdb": None,
            "metacritic": None,
            "trakt": None,
        }

        for service in ratings.keys():
            ratings[service] = (
                radarr_movie["ratings"].get(service.replace("_t", "T"), {}).get("value", None)
            )

            if ratings[service] and service in ["rotten_tomatoes", "metacritic"]:
                ratings[service] = ratings[service] / 10

        return ExternalRating(**ratings)

    def clean_movies(self, dry_run: bool = False) -> None:
        """
        Execute the movie cleanup process.

        Args:
            dry_run: If True, simulate the cleanup without actually deleting files
        """
        logger.info(f"Starting movie cleanup process... ({'DRY RUN' if dry_run else 'LIVE RUN'})")

        logger.info(f"Found {len(self.combined_movies)} movies to review from Radarr.")
        movies_to_delete = self._process_movies()

        self._log_statistics(movies_to_delete, len(self.combined_movies))
        self._delete_movies(movies_to_delete, dry_run)

    def _process_movies(self) -> List[MovieInfo]:
        """Process the list of Radarr movies in parallel."""

        # Partial function to avoid passing self and overseerr_requests repeatedly
        process_func = functools.partial(self._process_single_movie)

        # Process movies in parallel using ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=10) as executor:
            results = list(
                tqdm(
                    executor.map(process_func, self.combined_movies.items()),
                    total=len(self.combined_movies),
                    desc="Processing Movies",
                    unit="movies",
                    leave=False,
                )
            )

        # Filter out None results and combine valid TMDb IDs
        return [tmdb_id for tmdb_id in results if tmdb_id]

    def _process_single_movie(self, movie_item: tuple) -> Optional[str]:
        """Process a single movie and return its TMDb ID if it should be deleted."""
        tmdb_id, movie = movie_item

        if not tmdb_id:
            return None

        try:
            movie_info = self._get_movie_info(movie[0], tmdb_id)
            if self._should_delete_movie(movie_info):
                return tmdb_id
        except NotFound:
            pass
        except Exception as e:
            logger.error(f"Error processing movie {movie[0].get('title')}: {e}")

        return None

    def _determine_average_external_rating(self, movie_info: MovieInfo) -> float:
        """Determine the average external rating for a movie."""
        ratings = []

        for field in fields(movie_info.external_ratings):
            if getattr(movie_info.external_ratings, field.name):
                ratings.append(getattr(movie_info.external_ratings, field.name, None))

        return round(sum(ratings) / len(ratings), 1)

    def scrape_imdb_top_250(self) -> List[str]:
        """
        Scrape the IMDB Top 250 list and return the titles.
        """

        try:
            # Get the IMDB Top 250 page
            response = requests.get(
                "https://www.imdb.com/chart/top",
                headers={
                    "User-Agent": "Mozilla/5.0",
                },
                verify=False,
            )
            response.raise_for_status()

            # Parse the HTML
            soup = BeautifulSoup(response.text, "html.parser")

            # Find all movie titles in the Top 250
            top_250 = json.loads(
                "".join(soup.find("script", {"type": "application/ld+json"}).contents)
            )

            return [html.unescape(x["item"]["name"]) for x in top_250["itemListElement"]]

        except Exception as e:
            logger.error(f"Error retrieving IMDB Top 250: {e}")
            return []

    def _is_imdb_top_250(self, movie_info: MovieInfo) -> bool:
        """
        Check if a movie is currently in the IMDB Top 250 list by scraping the IMDB website.

        Args:
            movie_info: MovieInfo object containing movie details

        Returns:
            bool: True if movie is in IMDB Top 250, False otherwise
        """

        return movie_info.title in self.imdb_top_250

    def _determine_retention_days(self, movie_info: MovieInfo) -> int:
        """
        Determine how many days to retain a movie based on various criteria.

        Args:
            movie_info: MovieInfo object containing movie details

        Returns:
            Number of days to retain the movie
        """
        # If user rated the movie and rating is below low rating threshold
        if (
            movie_info.user_rating
            and movie_info.user_rating <= self.config.rating_threshold.low_rating
        ):
            return self.config.days_threshold.low_rating

        # If no user rating or external rating is low
        if not movie_info.user_rating or self._determine_average_external_rating(movie_info) < 3.5:
            # Check if non-admin requested the movie
            is_admin_request = (
                not movie_info.requested_by
                or movie_info.requested_by.lower() in self.config.admin_emails
            )
            return (
                self.config.days_threshold.admin
                if is_admin_request
                else self.config.days_threshold.user
            )

        return self.config.days_threshold.low_rating

    def _calculate_expiry_date(
        self,
        movie_info: MovieInfo,
    ) -> Optional[datetime]:
        """
        Calculate the expiry date for a movie based on the user type and watch history.

        Args:
            non_admin_request: Whether the movie was requested by a user vs an admin
            added_at: Datetime the movie was added to Plex
            last_watched: Datetime the movie was last watched

        Returns:
            Datetime when the movie will expire
        """
        # Movies with rating >= 2.5 stars (5/10) never expire
        # Check user rating first
        if movie_info.user_rating and movie_info.user_rating >= self.config.rating_threshold.admin:
            return None

        # Avoid deleting movies in the IMDB Top 250
        if self._is_imdb_top_250(movie_info):
            return None

        # Avoid deleting movies with high ratings from external sources (IMDB, Rotten Tomatoes, etc.)
        if self._determine_average_external_rating(movie_info) >= 8:
            return None

        # Use the most recent activity date
        last_activity = movie_info.last_watched or movie_info.added_at

        # Determine the retention days based on the user type and watch history
        retention_days = self._determine_retention_days(movie_info)

        return last_activity + timedelta(days=retention_days)

    def _is_expired(self, expires_at: Optional[datetime]) -> bool:
        """
        Check if a movie has expired based on the expiry date.

        Args:
            expires_at: Datetime when the movie will expire

        Returns:
            True if the movie has expired, False otherwise
        """
        return expires_at and datetime.now() >= expires_at

    def _will_expire_soon(self, expires_at: Optional[datetime], days: int = 30) -> bool:
        """
        Check if a movie will expire within a specified number of days.

        Args:
            expires_at: Datetime when the movie will expire
            days: Number of days to check for expiry

        Returns:
            True if the movie will expire within the specified days, False otherwise
        """
        return expires_at and datetime.now() <= expires_at <= datetime.now() + timedelta(days=days)

    def _get_movie_info(self, radarr_movie: dict, tmdb_id: str) -> MovieInfo:
        """
        Create a MovieInfo object with data from Plex and Radarr.

        Args:
            radarr_movie: Movie information from Radarr
            tmdb_id: TMDB ID of the movie

        Returns:
            MovieInfo object containing combined movie information

        Raises:
            NotFound: If the movie cannot be found in Plex
        """
        # Get the Overseerr request for the movie if it exists
        overseerr_request = next(
            iter(filter(lambda x: x["media"]["tmdbId"] == int(tmdb_id), self.overseerr_requests)),
            {},
        )

        plex_movie = self.plex.library.section("Movies").getGuid(f"tmdb://{tmdb_id}")
        movie_info = MovieInfo(
            title=radarr_movie["title"],
            tmdb_id=tmdb_id,
            radarr_id=radarr_movie["id"],
            added_at=plex_movie.addedAt,
            external_ratings=self.get_external_ratings(radarr_movie),
            requested_by=overseerr_request.get("requestedBy", {}).get("email", None),
            last_watched=self._get_last_watched(plex_movie),
            user_rating=plex_movie.userRating,
        )

        # Calculate the expiry date for this movie
        movie_info.expires_at = self._calculate_expiry_date(movie_info)

        if self._will_expire_soon(movie_info.expires_at):
            self.upcoming_movies.append(movie_info)

            tqdm.write(
                f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S,%f')[:-3]} - movie_cleaner - INFO - "
                f"{movie_info.title} will expire on "
                f"{movie_info.expires_at.strftime('%Y-%m-%d')}! "
                f"Last Watched: {movie_info.last_watched}, "
                f"Added: {movie_info.added_at}, "
                f"Rating: {movie_info.user_rating}, "
                f"Avg External Rating: {self._determine_average_external_rating(movie_info)}"
            )

        return movie_info

    def _get_last_watched(self, plex_movie) -> datetime | None:
        """
        Get the last watched timestamp for any user from Tautulli.

        Args:
            plex_movie: Plex movie object

        Returns:
            datetime of last watch or None if never watched
        """
        return self.tautulli.get_last_watched(plex_movie.ratingKey)

    def _should_delete_movie(self, movie: MovieInfo) -> bool:
        """
        Determine if a movie should be deleted based on expiration date.

        Args:
            movie: MovieInfo object to evaluate
            is_requested: Whether the movie was requested through Overseerr

        Returns:
            True if movie should be deleted, False if it should be kept
        """
        return self._is_expired(movie.expires_at)

    def _delete_movies(self, movies: List[str], dry_run: bool = False) -> None:
        """
        Delete movies from both UHD and streaming Radarr instances.

        Args:
            movies: List of MovieInfo objects to delete
            dry_run: If True, simulate deletion without actually deleting
        """
        for movie in movies:
            movie = self.combined_movies[movie]
            action = "Would delete" if dry_run else "Attempting to delete"
            logger.info(f"{action} {movie[0]['title']}...")

            if dry_run:
                continue

            deletion_methods = {"uhd": self.radarr_uhd, "hd": self.radarr_streaming}

            for m in movie:
                if deletion_methods[m["type"]].delete_movie(m["id"]):
                    logger.info("Done!")

    def _log_statistics(self, deleted: List[MovieInfo], total: int) -> None:
        """
        Log summary statistics of the cleanup operation.

        Args:
            deleted: List of MovieInfo objects that were deleted
            total: Total number of movies processed
        """
        logger.info(f"Movies Deleted: {len(deleted)}")
        logger.info(f"Movies Kept: {total - len(deleted)}")
        logger.info(f"Movies Scheduled for Deletion Soon: {len(self.upcoming_movies)}")
