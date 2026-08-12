"""Detailed in-dialog tutorial for Annual Seasonality."""

TUTORIAL = {
    "id": "annual_seasonality",
    "order": 30,
    "name": "Annual Seasonality Calendar",
    "matches": ("annual seasonality",),
    "window_matches": ("annual seasonality calendar",),
    "summary": (
        "Find tags with recurring yearly peaks, then inspect them through a "
        "calendar, graph, and sortable results table."
    ),
    "steps": [
        {
            "title": "Configure the database scan",
            "targets": ("spin_min_posts", "spin_workers", "spin_batch"),
            "body": (
                "Minimum Total Posts removes noisy rare tags and requires a new "
                "scan when changed. Workers improve speed; Batch Size trades more "
                "RAM for throughput. Conservative values are safest on small systems."
            ),
        },
        {
            "title": "Choose tag categories",
            "targets": (
                "chks.artist", "chks.copyright", "chks.character",
                "chks.general", "chks.meta",
            ),
            "body": (
                "Artist, Copyright, Character, General, and Meta determine which "
                "tag columns supply candidates. Scanning fewer categories is "
                "faster and makes the final table more focused."
            ),
        },
        {
            "title": "Set seasonal quality filters",
            "targets": (
                "spin_window", "spin_score", "spin_max_year", "spin_recurrence",
            ),
            "body": (
                "Peak Window groups nearby days into one season. Min Score "
                "requires a stronger peak; Max Peak Year % rejects one-off events; "
                "Min Recurrence requires the pattern across multiple years."
            ),
        },
        {
            "title": "Filter names without rescanning",
            "targets": ("txt_tag_search", "btn_apply"),
            "body": (
                "Tag Search Filter narrows calculated results by name and supports "
                "<b>*wildcards*</b> and negative terms. Click Apply Filters after "
                "changing text or live thresholds; this does not rescan the database."
            ),
        },
        {
            "title": "Scan, save, or load a cache",
            "targets": ("btn_load", "btn_save", "btn_analyze"),
            "body": (
                "<b>Run Database Scan</b> calculates seasonal source data. Save "
                "the completed result for later sessions, or Load Cache to avoid "
                "repeating that expensive pass. The status line explains cache state."
            ),
        },
        {
            "title": "Use the calendar heatmap",
            "targets": ("lbl_cal_view", "btn_reset_view"),
            "body": (
                "Brighter calendar dates contain stronger or more numerous tag "
                "peaks. Select a date to focus the graph and result table. Reset "
                "to Global Heat restores the all-date overview."
            ),
        },
        {
            "title": "Compare graph modes",
            "targets": ("radio_annual", "radio_history", "chk_normalize"),
            "body": (
                "Annual Overlay aligns all years onto one 365-day cycle, making "
                "recurrence easy to compare. All-Time History preserves real "
                "chronology. Normalize compares curve shape instead of volume."
            ),
        },
        {
            "title": "Interpret and use seasonal tags",
            "targets": (
                "table", "btn_include", "btn_exclude", "btn_search", "btn_browser",
            ),
            "body": (
                "The table reports peak date, seasonal score, window posts, "
                "background rate, concentration, and spiked years. Select a tag "
                "to include/exclude it, search it alone, or open it on Danbooru."
            ),
        },
    ],
}

TUTORIAL["more_info"] = (
    "Seasonality separates recurring calendar behavior from one-time popularity "
    "spikes. Strong results have enough posts, concentrated timing, and evidence "
    "across multiple years."
)

_MORE_INFO = {
    "Configure the database scan": "Scan settings determine the reusable base cache. Increase minimum posts to reduce noise and output size. More workers are not always faster when storage speed is the bottleneck.",
    "Choose tag categories": "General tags are numerous and take the most work. Starting with Character or Copyright can produce a faster, easier-to-understand first scan.",
    "Set seasonal quality filters": "A narrow peak window favors date-specific events; a wider window captures seasons and holidays. Recurrence protects against a single viral year being labeled seasonal.",
    "Filter names without rescanning": "Name filtering operates on already-calculated rows, so experiment freely. Combine a wildcard with a negative term to explore a naming family while removing a known branch.",
    "Scan, save, or load a cache": "Cache files preserve expensive aggregate counts, not your current visual selection. Save after a successful scan and name caches according to their scan settings.",
    "Use the calendar heatmap": "A selected day changes the table target to tags peaking near that date. Neighboring bright cells may represent one multi-day event rather than separate trends.",
    "Compare graph modes": "Annual Overlay tests repeated shape; History reveals whether the effect exists every year or is dominated by recent growth. Use both before calling a tag truly seasonal.",
    "Interpret and use seasonal tags": "High score plus many spiked years is stronger evidence than peak count alone. Send a selected tag to the main search to inspect the actual posts behind the statistic.",
}
for _step in TUTORIAL["steps"]:
    _step["more_info"] = _MORE_INFO[_step["title"]]
