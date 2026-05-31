from PyQt6.QtWidgets import QLabel, QScrollArea, QVBoxLayout, QWidget

C_TEXT1  = "#EDEDED"
C_TEXT2  = "#A1A1A1"
C_ACCENT = "#E66B66"

_SECTIONS = [
    (
        "Overview",
        "OSINT Camera Finder aggregates publicly available webcam feeds from multiple sources "
        "into a searchable local database. All data is stored in a local SQLite file (cameras.db). "
        "No data leaves your machine.",
    ),
    (
        "Tabs",
        "<b style='color:#EDEDED'>Scan</b> — Choose a data source, configure any source-specific "
        "options (country, state), and press Start Scan. The scanner runs in a background thread "
        "and streams results into the database in real time. A live log and camera count update "
        "during the scan. Press Stop to interrupt gracefully.<br><br>"

        "<b style='color:#EDEDED'>Database</b> — Browse and filter all cameras in the local "
        "database. Use the Source, Country, and Status dropdowns to narrow results. Check one or "
        "more Category boxes to filter by camera type. The Search box matches against camera name, "
        "city, and URL. Apply runs the filter; Clear resets all filters. Results are paginated at "
        "200 rows per page.<br><br>"

        "<b style='color:#EDEDED'>Export</b> — Export filtered cameras to a JSON file. Configure "
        "the same filter options as the Database tab, click Preview Count to verify the match "
        "count, then choose an output path and click Export JSON.<br><br>"

        "<b style='color:#EDEDED'>Sources</b> — Define custom HTTP API sources. Provide an "
        "endpoint URL, optional authentication headers, pagination style, and a field mapping "
        "(jmespath paths from the JSON response to camera schema fields). Use Test to preview the "
        "first 10 results before saving.<br><br>"

        "<b style='color:#EDEDED'>Settings</b> — Store API keys for sources that require them "
        "(currently: Windy Webcams). Keys are saved to a local .env file and never transmitted.",
    ),
    (
        "Built-in Sources",
        "<b style='color:#EDEDED'>Insecam</b> — Public camera directory. Filter by country.<br><br>"
        "<b style='color:#EDEDED'>FAA WeatherCams</b> — US Federal Aviation Administration weather "
        "camera network. No filter needed — all US cameras are returned in a single request.<br><br>"
        "<b style='color:#EDEDED'>OpenStreetMap</b> — Camera nodes tagged in OSM contributor data. "
        "Optional country filter. Only cameras with a URL or sufficient location data are stored.<br><br>"
        "<b style='color:#EDEDED'>Windy Webcams</b> — Global webcam network. Requires a free Windy "
        "API key set in the Settings tab. Optional country filter.<br><br>"
        "<b style='color:#EDEDED'>US DOT Traffic</b> — US Department of Transportation traffic "
        "cameras. Currently covers New York (NY 511 open feed). Filter by state.",
    ),
    (
        "Categories",
        "Cameras are automatically assigned a category based on keywords in their name and type "
        "field:<br><br>"
        "<b style='color:#EDEDED'>weather</b> — meteorological / environmental monitoring<br>"
        "<b style='color:#EDEDED'>traffic</b> — road, highway, and intersection cameras<br>"
        "<b style='color:#EDEDED'>tourist</b> — scenic, city, and landmark views<br>"
        "<b style='color:#EDEDED'>aviation</b> — airport and airfield cameras<br>"
        "<b style='color:#EDEDED'>nature</b> — wildlife, parks, mountains, beaches<br>"
        "<b style='color:#EDEDED'>security</b> — surveillance and monitoring installations<br>"
        "<b style='color:#EDEDED'>unknown</b> — could not be categorized automatically",
    ),
    (
        "Custom Sources",
        "Any JSON REST API can be added as a custom source in the Sources tab.<br><br>"
        "The endpoint must return a JSON array, or an object containing one. Map response fields "
        "to the camera schema using jmespath dot-notation paths (e.g. <tt>location.lat</tt> for a "
        "nested latitude field).<br><br>"
        "<b style='color:#EDEDED'>Pagination styles:</b><br>"
        "<b style='color:#EDEDED'>none</b> — single request, no pagination<br>"
        "<b style='color:#EDEDED'>offset</b> — increments an integer offset parameter<br>"
        "<b style='color:#EDEDED'>page</b> — increments a page number parameter<br>"
        "<b style='color:#EDEDED'>cursor</b> — follows a next-cursor field in each response<br><br>"
        "API keys can be stored in the .env file and injected into URLs, headers, or params using "
        "<tt>{ENV_VAR_NAME}</tt> syntax (uppercase letters, numbers, and underscores only).<br><br>"
        "The <b style='color:#EDEDED'>camera_id</b> field mapping is required — it is used for "
        "deduplication across scans.",
    ),
    (
        "Database File",
        "The SQLite database is stored at <tt>cameras.db</tt> in the project directory. It is "
        "created automatically on first run.<br><br>"
        "Cameras are deduplicated by source + camera_id. Re-scanning a source updates existing "
        "records rather than creating duplicates, and reports new / updated / unchanged counts.<br><br>"
        "Cameras with no URL and no usable location data (coordinates or city + country) are "
        "silently discarded and never written to the database.<br><br>"
        "You can delete <tt>cameras.db</tt> at any time to start fresh — all scanned data will be lost.",
    ),
]


class HelpPanel(QWidget):
    def __init__(self):
        super().__init__()
        self._build()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(40, 30, 40, 30)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)

        inner = QWidget()
        inner_lay = QVBoxLayout(inner)
        inner_lay.setSpacing(16)
        inner_lay.setContentsMargins(0, 0, 0, 0)

        # Title
        title = QLabel("How to use OSINT Camera Finder")
        title.setStyleSheet(f"color: {C_ACCENT}; font-size: 18px; font-weight: 700;")
        inner_lay.addWidget(title)

        # Divider
        divider = QLabel()
        divider.setFixedHeight(1)
        divider.setStyleSheet(f"background-color: #333333;")
        inner_lay.addWidget(divider)
        inner_lay.addSpacing(8)

        for heading, body in _SECTIONS:
            h = QLabel(heading)
            h.setStyleSheet(f"color: {C_TEXT1}; font-size: 15px; font-weight: 600;")
            inner_lay.addWidget(h)

            b = QLabel(body)
            b.setStyleSheet(f"color: {C_TEXT2}; font-size: 13px;")
            b.setWordWrap(True)
            b.setTextFormat(b.textFormat().RichText)
            inner_lay.addWidget(b)

            sep = QLabel()
            sep.setFixedHeight(1)
            sep.setStyleSheet("background-color: #252525;")
            inner_lay.addWidget(sep)

        inner_lay.addStretch()
        scroll.setWidget(inner)
        root.addWidget(scroll)
