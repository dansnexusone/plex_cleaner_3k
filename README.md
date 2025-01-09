

## Overview

plex_cleaner_3k is an automated solution for managing your Plex movie library by intelligently cleaning up movies based on watch history, ratings, and custom retention rules. It integrates with Radarr, Overseerr, and Tautulli to make informed decisions about which content to keep or remove.

## Features

- Automated cleanup of movies from both 4K/UHD and 1080p libraries
- Smart retention rules based on:
  - Plex user ratings
  - External ratings (IMDB, Rotten Tomatoes, TMDB, Metacritic, Trakt)
  - Watch history
  - Request source (admin vs regular users)
  - IMDB Top 250 status
- Service integrations:
  - Plex Media Server
  - Dual Radarr instances (4K and 1080p)
  - Overseerr
  - Tautulli
- Dry-run mode for testing deletions
- Detailed logging

## Requirements

- Python 3.12+
- Plex Media Server
- Radarr (4K and 1080p instances)
- Overseerr
- Tautulli
- Docker (optional)

## Installation

### Option 1: Using Docker

1. Clone the repository:

```bash
git clone https://github.com/yourusername/plex_cleaner_3k.git
cd plex_cleaner_3k
```

2. Create configuration files (see Configuration section)

3. Build and run with Docker:

```bash
docker build -t plex-cleaner .
docker run -v $(pwd)/config.yaml:/app/config.yaml --env-file .env plex-cleaner
```

### Option 2: Manual Installation

1. Clone the repository
2. Set up virtual environment:

```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
.\venv\Scripts\activate   # Windows
```

3. Install dependencies:

```bash
pip install -r requirements.txt
```

## Configuration

The application uses two configuration files:

1. `config.yaml` for general settings
2. `.env` for sensitive information (API keys, passwords)

### Environment Variables (.env)

Create a `.env` file in the project root:

```bash
PLEX_TOKEN=your-plex-token
TAUTULLI_API_KEY=your-tautulli-api-key
RADARR_4K_API_KEY=your-radarr-4k-api-key
RADARR_1080P_API_KEY=your-radarr-hd-api-key
OVERSEERR_API_KEY=your-overseerr-api-key
OVERSEERR_PASSWORD=your-overseerr-password
```

### Configuration File (config.yaml)

Create a `config.yaml` file:

```yaml
plex:
  url: "http://plex.local:32400"

tautulli:
  url: "http://tautulli.local:8181"

radarr:
  4k:
    url: "http://radarr-4k.local:7878"
  1080p:
    url: "http://radarr-hd.local:7878"

overseerr:
  url: "http://overseerr.local:5055"
  email: "your-email@domain.com"

admin_emails:
  - "admin1@domain.com"
  - "admin2@domain.com"

deletion_threshold:
  days:
    users:
      admin: 180  # Keep admin requests for 6 months
      user: 90    # Keep user requests for 3 months
    rules:
      low_rated: 30  # Remove low-rated content after 1 month
  rating:
    users:
      admin: 5  # Admin rating threshold
      user: 5   # User rating threshold
    rules:
      low: 3    # Low rating threshold
```

## Usage

### Basic Usage

Run the cleaner:

```bash
python main.py
```

### Dry Run Mode

Test without deleting:

```bash
python main.py --dry-run
```

### Docker Usage

```bash
# Normal run
docker run -v $(pwd)/config.yaml:/app/config.yaml --env-file .env plex-cleaner

# Dry run
docker run -v $(pwd)/config.yaml:/app/config.yaml --env-file .env plex-cleaner --dry-run
```

## How It Works

The cleaner evaluates movies based on:

1. Watch history from Tautulli
2. User ratings from Plex
3. External ratings (IMDB, Rotten Tomatoes, etc.)
4. Request source from Overseerr
5. Age of content

### Retention Rules

- Movies rated ≥ 2.5 stars are preserved
- IMDB Top 250 movies are always kept
- High external ratings (≥ 8/10) protect content
- Time-based rules:
  - Admin requests: 180 days
  - User requests: 90 days
  - Low-rated content: 30 days

## Project Structure

```
plex_cleaner_3k/
├── models/
│   ├── config.py          # Configuration dataclasses
│   ├── external_rating.py # Rating data structures
│   └── movie_info.py      # Movie metadata class
├── services/
│   ├── config.py          # Config management
│   ├── overseerr.py       # Overseerr integration
│   ├── radarr.py         # Radarr API client
│   └── tautulli.py       # Tautulli integration
├── .env                   # Environment variables (secrets)
├── config.yaml           # YAML configuration file
├── main.py              # CLI entry point
├── movie_cleaner.py     # Core cleaning logic
├── requirements.txt     # Python dependencies
└── Dockerfile          # Container definition
```

## Security Notes

- Never commit your `.env` file to version control
- The `.env` file is included in `.gitignore` by default
- When using Docker, pass environment variables using the `--env-file` flag
- For production deployments, consider using a secrets management solution

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## License

MIT License - See LICENSE file for details
