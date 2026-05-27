# OSINT Camera Finder

An OSINT tool for discovering and cataloguing publicly accessible cameras worldwide, with full location metadata including coordinates, city, region, and country.

## Sources

- **Insecam** — open webcams indexed by country, with camera type, lat/long, city, and region
- **FAA WeatherCams** — aviation weather cameras across the US and internationally, with site name, ICAO code, state, coordinates, and direct loop viewer links

## Output

Each source produces a JSON file per run:

- `insecam_<country_code>.json` — one entry per camera with URL, metadata, and coordinates
- `faa_weathercams.json` — one entry per camera with site info, coordinates, and direct access URLs

## Usage

```bash
pip install requests colorama
python3 webanator-json.py
```

Choose source at the prompt, then select a country (Insecam) or proceed directly (FAA WeatherCams).

## About

Developed by [Modular Misfits](https://github.com/Modular-Misfits)
