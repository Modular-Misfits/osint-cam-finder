#!/usr/bin/env python3

import re
import json
import socket
import subprocess
import requests
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from colorama import Fore as colour

RED = colour.RED
CYAN = colour.CYAN
BLUE = colour.BLUE
WHITE = colour.WHITE
GREEN = colour.GREEN
YELLOW = colour.YELLOW

def banner():
    subprocess.run("clear", shell=True)
    print("")
    colors = [BLUE, RED, WHITE] * 10
    for i, line in enumerate("""
██╗    ██╗███████╗██████╗  █████╗ ███╗   ██╗ █████╗ ████████╗ ██████╗ ██████╗
██║    ██║██╔════╝██╔══██╗██╔══██╗████╗  ██║██╔══██╗╚══██╔══╝██╔═══██╗██╔══██╗
██║ █╗ ██║█████╗  ██████╔╝███████║██╔██╗ ██║███████║   ██║   ██║   ██║██████╔╝
██║███╗██║██╔══╝  ██╔══██╗██╔══██║██║╚██╗██║██╔══██║   ██║   ██║   ██║██╔══██╗
╚███╔███╔╝███████╗██████╔╝██║  ██║██║ ╚████║██║  ██║   ██║   ╚██████╔╝██║  ██║
 ╚══╝╚══╝ ╚══════╝╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═══╝╚═╝  ╚═╝   ╚═╝    ╚═════╝ ╚═╝  ╚═╝
    """.strip().split("\n")):
        print(f"{colors[i]} {line}")
    print("")
    print(f"{RED}[{WHITE}!!!{RED}] {BLUE}Tool-Name {WHITE}: {RED}OSINT Camera Finder")
    print(f"{RED}[{WHITE}!!!{RED}] {BLUE}Github    {WHITE}: {RED}https://github.com/Modular-Misfits/osint-cam-finder")
    print(f"{RED}[{WHITE}!!!{RED}] {BLUE}Coded By  {WHITE}: {RED}Chief Misfit")

banner()
print("")
print(f"{BLUE}========================================================")
print(f"{RED}[{WHITE}???{RED}] Checking internet connection{BLUE}...")

try:
    connect_google = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    CONNECTION = connect_google.connect_ex(('www.google.com', 80))
    if CONNECTION == 0:
        print(f"{GREEN}[{BLUE}+++{GREEN}] Internet Connection Established: {CYAN}Proceeding")
        print(f"{BLUE}========================================================")
        banner()
    else:
        raise socket.gaierror
except socket.gaierror:
    print(f"{RED}[{WHITE}!!!{RED}] No Internet Connection Found{BLUE}: {RED}Exiting")
    print(f"{BLUE}========================================================")
    exit()

B = BLUE
R = RED
W = WHITE

print("")
source_option = input(f"""{B}╔════════════════════════════════════════════╗
{R}║ {R}[{W}1{R}] {W}Insecam (worldwide open webcams)   {R}║
{W}║ {R}[{W}2{R}] {W}FAA WeatherCams (aviation)         {W}║
{B}╚════════════════════════════════════════════╝

{RED}[{WHITE}?{RED}] {WHITE}Choose source{BLUE}: """)

if source_option not in ("1", "2"):
    print(f"{RED}[{WHITE}!{RED}] Invalid option")
    exit()

# ─── FAA WeatherCams path ────────────────────────────────────────────────────

if source_option == "2":
    print("")
    print(f"{RED}[{WHITE}!{RED}] {WHITE}Fetching FAA WeatherCams data{B}...")
    print("")

    headers = {
        "Referer": "https://weathercams.faa.gov/",
        "Origin": "https://weathercams.faa.gov",
        "Accept": "application/json",
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    }

    try:
        resp = requests.get("https://weathercams.faa.gov/api/sites", headers=headers, timeout=30)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        print(f"{RED}[{WHITE}!{RED}] Failed to fetch FAA data: {e}")
        exit()

    results = []
    sites = data.get("payload", [])
    for site in sites:
        site_name = site.get("siteName", "")
        state = site.get("state", "")
        country = site.get("country", "")
        site_lat = site.get("latitude")
        site_lon = site.get("longitude")
        elevation = site.get("elevation")
        timezone = site.get("timeZone", "")
        icao = site.get("icao", "")

        for cam in site.get("cameras", []):
            cam_id = cam.get("cameraId")
            entry = {
                "source": "FAA WeatherCams",
                "camera_id": cam_id,
                "camera_name": cam.get("cameraName", ""),
                "camera_direction": cam.get("cameraDirection", ""),
                "site_name": site_name,
                "icao": icao,
                "latitude": cam.get("latitude") or site_lat,
                "longitude": cam.get("longitude") or site_lon,
                "elevation_ft": elevation,
                "state": state,
                "country": country,
                "timezone": timezone,
                "in_maintenance": cam.get("cameraInMaintenance", False),
                "out_of_order": cam.get("cameraOutOfOrder", False),
                "last_success": cam.get("cameraLastSuccess", ""),
                "camera_loop_url": f"https://weathercams.faa.gov/cameras/cameraSite/{site.get('siteId')}/details/camera/{cam_id}/loop-full",
                "latest_images_url": f"https://weathercams.faa.gov/api/cameras/{cam_id}/images",
            }
            results.append(entry)
            print(f"{R}[{B}+{R}] {W}{site_name} {R}| {W}{cam.get('cameraName')} ({cam.get('cameraDirection')}) {R}| {W}{state}, {country} {R}| {W}{entry['latitude']}, {entry['longitude']}")

    output_file = "faa_weathercams.json"
    with open(output_file, "w") as f:
        json.dump(results, f, indent=2)

    print("")
    print(f"{GREEN}[{BLUE}+++{GREEN}] Done! {len(results)} cameras written to {WHITE}{output_file}")
    exit()

# ─── Insecam path ────────────────────────────────────────────────────────────

print("")
option = input(f"""{B}╔════════════════════════════════════════════════════════════════════════════╗
{R}║ {R}[{W}1{R}] {W}USA                         {R}║ {R}[{W}13{R}] {W}China                               {R}║
{W}║ {R}[{W}2{R}] {W}Canada                      {W}║ {R}[{W}14{R}] {W}Japan                               {W}║
{B}║ {R}[{W}3{R}] {W}Mexico                      {B}║ {R}[{W}15{R}] {W}North Korea                         {B}║
{R}║ {R}[{W}4{R}] {W}Brazil                      {R}║ {R}[{W}16{R}] {W}Taiwan                              {R}║
{W}║ {R}[{W}5{R}] {W}Romania                     {W}║ {R}[{W}17{R}] {W}American Samoa                      {W}║
{B}║ {R}[{W}6{R}] {W}Nigeria                     {B}║ {R}[{W}18{R}] {W}Netherlands                         {B}║
{R}║ {R}[{W}7{R}] {W}South Africa                {R}║ {R}[{W}19{R}] {W}India                               {R}║
{W}║ {R}[{W}8{R}] {W}France                      {W}║ {R}[{W}20{R}] {W}Switzerland                         {W}║
{B}║ {R}[{W}9{R}] {W}Madagascar                  {B}║ {R}[{W}21{R}] {W}Tanzania                            {B}║
{R}║ {R}[{W}10{R}] {W}Russia                     {R}║ {R}[{W}22{R}] {W}Belarus                             {R}║
{W}║ {R}[{W}11{R}] {W}Germany                    {W}║ {R}[{W}23{R}] {W}Estonia                             {W}║
{B}║ {R}[{W}12{R}] {W}Finland                    {B}║ {R}[{W}24{R}] {W}Slovenia                            {B}║
{R}╚════════════════════════════════════════════════════════════════════════════╝

{RED}[{WHITE}?{RED}] {WHITE}Choose the country you would like to gather webcams from{BLUE}: """)

country_map = {
    "1": ("US", "United States"),
    "2": ("CA", "Canada"),
    "3": ("MX", "Mexico"),
    "4": ("BR", "Brazil"),
    "5": ("RO", "Romania"),
    "6": ("NG", "Nigeria"),
    "7": ("ZA", "South Africa"),
    "8": ("FR", "France"),
    "9": ("MG", "Madagascar"),
    "10": ("RU", "Russia"),
    "11": ("DE", "Germany"),
    "12": ("FI", "Finland"),
    "13": ("CN", "China"),
    "14": ("JP", "Japan"),
    "15": ("NK", "North Korea"),
    "16": ("TW", "Taiwan"),
    "17": ("AS", "American Samoa"),
    "18": ("NL", "Netherlands"),
    "19": ("IN", "India"),
    "20": ("CH", "Switzerland"),
    "21": ("TZ", "Tanzania"),
    "22": ("BY", "Belarus"),
    "23": ("EE", "Estonia"),
    "24": ("SI", "Slovenia"),
}

if option == "":
    print(f"{RED}[{WHITE}!{RED}] You must pick an option")
    exit()
if option not in country_map:
    print("[!] Invalid option selected")
    print("[!] Aborting")
    exit()

country_code, country_name = country_map[option]

banner()
print("")
print(f"{RED}[{WHITE}!{RED}] {WHITE}Scanning for webcams in{B}: {RED}{country_name}")
print("")

USER_AGENT = "Mozilla/5.0 (Linux; Android 12; SAMSUNG SM-A125F) AppleWebKit/537.36 (KHTML, like Gecko) SamsungBrowser/19.0 Chrome/102.0.5005.125 Mobile Safari/537.36"
THREAD_POOL_SIZE = 20
# (connect_timeout, read_timeout) — cameras that accept TCP but never reply get killed at 5s read
CONNECT_TIMEOUT = 4
READ_TIMEOUT = 5

results = []
results_lock = threading.Lock()
thread_local = threading.local()


def get_session():
    if not hasattr(thread_local, "session"):
        s = requests.Session()
        s.headers.update({"User-Agent": USER_AGENT})
        thread_local.session = s
    return thread_local.session


def fetch_camera_detail(cam_id):
    detail_url = f"http://www.insecam.org/en/view/{cam_id}/"
    try:
        resp = get_session().get(detail_url, timeout=(CONNECT_TIMEOUT, READ_TIMEOUT))
        html = resp.text

        title_match = re.search(r'<title>\s*View\s+(.*?)\s+camera\s+in\s+(.*?)\s*</title>', html, re.IGNORECASE)
        cam_type = title_match.group(1).strip() if title_match else ""
        location_raw = title_match.group(2).strip() if title_match else ""

        coords = re.findall(r'(?:setView|marker|LatLng)\s*\(\s*\[?\s*(-?[\d.]+)\s*,\s*(-?[\d.]+)', html, re.IGNORECASE)
        latitude = float(coords[0][0]) if coords else None
        longitude = float(coords[0][1]) if coords else None

        city, region = "", ""
        desc_match = re.search(r'Watch live cam located in ([^\r\n<]+)', html, re.IGNORECASE)
        if desc_match:
            raw = desc_match.group(1).strip()
            region_match = re.search(r'region\s+(\S+)\s+(.*)', raw)
            if region_match:
                region = region_match.group(1).strip()
                city = region_match.group(2).strip()
        elif location_raw:
            parts = [p.strip() for p in location_raw.split(",")]
            if len(parts) >= 2:
                city = parts[-1]

        return {
            "camera_type": cam_type,
            "latitude": latitude,
            "longitude": longitude,
            "city": city,
            "region": region,
            "location_raw": location_raw,
        }
    except Exception:
        return {}


def scan_and_enrich(cam_id, cam_url):
    try:
        resp = get_session().get(cam_url, timeout=(CONNECT_TIMEOUT, READ_TIMEOUT))
        status = resp.status_code
        server = resp.headers.get("Server", "")
    except requests.exceptions.ConnectionError:
        status, server = None, ""
    except Exception:
        status, server = None, ""

    detail = fetch_camera_detail(cam_id)

    entry = {
        "source": "Insecam",
        "url": cam_url,
        "camera_id": cam_id,
        "camera_type": detail.get("camera_type", ""),
        "http_status": status,
        "server": server,
        "country": country_name,
        "country_code": country_code,
        "region": detail.get("region", ""),
        "city": detail.get("city", ""),
        "location_raw": detail.get("location_raw", ""),
        "latitude": detail.get("latitude"),
        "longitude": detail.get("longitude"),
    }

    with results_lock:
        results.append(entry)

    lat = detail.get("latitude", "")
    lon = detail.get("longitude", "")
    city_display = detail.get("city", "") or detail.get("location_raw", "")
    print(f"{R}[{B}+{R}] {W}{cam_url} {R}[{W}{server}{R}] {R}[{W}{status}{R}] {R}| {W}{city_display} {R}| {W}{lat}, {lon}")

    return entry


# Collect all unique (cam_id, cam_url) pairs across all pages first
list_session = requests.Session()
list_session.headers.update({"User-Agent": USER_AGENT})
all_pairs = {}  # cam_id -> cam_url, deduplicates by ID

try:
    for page in range(1, 365):
        resp = list_session.get(
            f"http://www.insecam.org/en/bycountry/{country_code}/?page={page}",
            timeout=(CONNECT_TIMEOUT, READ_TIMEOUT),
        )
        resp.raise_for_status()
        html = resp.text

        # Match each camera block: find the view ID then the first IP:port src after it
        for m in re.finditer(r'/en/view/(\d+)/', html):
            cam_id = m.group(1)
            if cam_id in all_pairs:
                continue
            # Look for IP:port URL within the next 600 chars of this match
            tail = html[m.start():m.start() + 600]
            url_match = re.search(r'src="(http://\d+\.\d+\.\d+\.\d+:\d+[^"]*)"', tail)
            if url_match:
                all_pairs[cam_id] = url_match.group(1)

        # Stop when the page has no camera entries at all
        if not re.search(r'/en/view/\d+/', html):
            break

except KeyboardInterrupt:
    print(f"\n{RED}[{WHITE}!{RED}] Collection terminated by user — processing gathered cameras")

print(f"\n{GREEN}[{BLUE}+++{GREEN}] {WHITE}Found {len(all_pairs)} unique cameras — enriching with detail pages...")
print("")

output_file = f"insecam_{country_code.lower()}.json"

def save_results():
    with open(output_file, "w") as f:
        json.dump(results, f, indent=2)

# Per-future deadline: slightly longer than the combined network timeouts to catch
# anything (SSL stall, proxy weirdness) that slips past requests' own timeout.
# Each future is checked individually — one slow camera never blocks the rest.
FUTURE_DEADLINE = CONNECT_TIMEOUT + READ_TIMEOUT + 3

try:
    with ThreadPoolExecutor(max_workers=THREAD_POOL_SIZE) as executor:
        futures = {
            executor.submit(scan_and_enrich, cam_id, cam_url): cam_id
            for cam_id, cam_url in all_pairs.items()
        }
        done = 0
        total = len(futures)
        for future in as_completed(futures):
            cam_id = futures[future]
            try:
                future.result(timeout=FUTURE_DEADLINE)
            except TimeoutError:
                print(f"{YELLOW}[{WHITE}!{YELLOW}] Camera {cam_id} timed out — skipping")
            except Exception:
                pass
            done += 1
            if done % 50 == 0:
                print(f"{BLUE}[{WHITE}...{BLUE}] {done}/{total} cameras processed")
except KeyboardInterrupt:
    print(f"\n{RED}[{WHITE}!{RED}] Enrichment terminated by user — saving partial results")

save_results()
print("")
print(f"{GREEN}[{BLUE}+++{GREEN}] Done! {len(results)} cameras written to {WHITE}{output_file}")
