import argparse
import logging

from movie_cleaner import MovieCleaner


def main():
    parser = argparse.ArgumentParser(
        description="Clean up movies based on watch history and ratings."
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Simulate cleanup without actually deleting files"
    )
    args = parser.parse_args()

    # Configure logging
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    cleaner = MovieCleaner()
    cleaner.clean_movies(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
