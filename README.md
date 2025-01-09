
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

2. Build and run with Docker:

```bash
docker build -t plex-cleaner .
docker run -v $(pwd)/config.yaml:/app/config.yaml plex-cleaner
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

Create a `config.yaml` file:

```yaml
plex:
  url: "http://plex.local:32400"
  token: "your-plex-token"

tautulli:
  url: "http://tautulli.local:8181"
  api_key: "your-tautulli-api-key"

radarr:
  4k:
    url: "http://radarr-4k.local:7878"
    api_key: "your-radarr-4k-api-key"
  1080p:
    url: "http://radarr-hd.local:7878"
    api_key: "your-radarr-hd-api-key"

overseerr:
  url: "http://overseerr.local:5055"
  api_key: "your-overseerr-api-key"
  email: "your-email@domain.com"
  password: "your-password"

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
      admin: 5.0  # Admin rating threshold
      user: 3.0   # User rating threshold
    rules:
      low: 2.5    # Low rating threshold
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
docker run -v $(pwd)/config.yaml:/app/config.yaml plex-cleaner

# Dry run
docker run -v $(pwd)/config.yaml:/app/config.yaml plex-cleaner --dry-run
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
├── config.yaml               # YAML configuration file
├── main.py               # CLI entry point
├── movie_cleaner.py      # Core cleaning logic
├── requirements.txt      # Python dependencies
└── Dockerfile           # Container definition
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## License

MIT License - See LICENSE file for details
