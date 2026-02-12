# Archive Data

This directory contains historical data archives required for the Red Sox dashboard.

## Required Files

The following files should be present in this directory for the scripts to function correctly without re-fetching all historical data:

1.  **`redsox_historic_batting_gamelogs.parquet`**
    *   **Description**: Historical batting game logs for the Red Sox (1901-present).
    *   **Used by**: `scripts/10_fetch_process_historic_batting_gamelogs.py`
    *   **Generation**: This file is generated/updated by script `10`. If missing, the script may attempt to fetch data or fail if not configured to fetch full history.

2.  **`redsox_historic_pitching_gamelogs.parquet`**
    *   **Description**: Historical pitching game logs for the Red Sox (1901-present).
    *   **Used by**: `scripts/12_fetch_process_historic_pitching_gamelogs.py`
    *   **Generation**: This file is generated/updated by script `12`.

3.  **`redsox_standings_1901_present.parquet`**
    *   **Description**: Historical standings and game results (1901-present).
    *   **Used by**: `scripts/04_fetch_process_standings.py` (indirectly via `data/standings` but good to have archived).
    *   **Generation**: Use `scripts/29_fetch_historical_standings.py` to generate this.

## How to Generate

To generate these archives from scratch (warning: this may take time and hit API rate limits):

1.  **Standings**:
    ```bash
    python scripts/29_fetch_historical_standings.py --start-year 1901
    ```
    Copy the resulting parquet file from `data/standings` to `data/archive`.

2.  **Batting/Pitching Gamelogs**:
    Run scripts `10` and `12`. You may need to adjust them to force a full historical fetch if the archives are missing.

## S3 Storage

These files are also stored in S3 at:
*   `s3://stilesdata.com/redsox/data/archive/`

The scripts are configured to try downloading from S3 if local files are missing.
