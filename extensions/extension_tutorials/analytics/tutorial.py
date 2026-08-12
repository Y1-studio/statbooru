"""Detailed in-dialog tutorial for Tag Analytics."""

TUTORIAL = {
    "id": "analytics",
    "order": 10,
    "name": "Tag Analytics",
    "matches": ("tag analytics",),
    "window_matches": ("tag analytics dashboard",),
    "summary": (
        "Analyze dates, ratings, characters, copyrights, artists, and general "
        "tags within the current main-window result set."
    ),
    "steps": [
        {
            "title": "What this dashboard analyzes",
            "targets": ("tabs",),
            "tab": ("tabs", 0),
            "body": (
                "Tag Analytics uses the current main-window search results. Run "
                "a search first; the extension button remains disabled without "
                "results. Reopen the dashboard after changing the query or filters "
                "to analyze the new set."
            ),
        },
        {
            "title": "Choose the date resolution and chart",
            "targets": ("date_combo", "chart_combo"),
            "tab": ("tabs", 0),
            "body": (
                "<b>Year</b> is best for long-term growth, <b>Month</b> reveals "
                "seasonal detail, and <b>Day</b> suits short ranges. Columns "
                "emphasize individual periods; Line emphasizes overall direction."
            ),
        },
        {
            "title": "Compare percentages or absolute volume",
            "targets": ("date_norm",),
            "tab": ("tabs", 0),
            "body": (
                "Enable <b>Normalize</b> to show each period as a percentage of "
                "all matching posts. This helps compare differently sized ranges. "
                "Leave it off when exact upload volume is the important measure."
            ),
        },
        {
            "title": "Smooth short-term noise",
            "targets": ("date_smooth", "date_window"),
            "tab": ("tabs", 0),
            "body": (
                "<b>Smooth Data</b> applies a moving average. Window controls how "
                "many adjacent periods contribute: a small window preserves local "
                "changes; a large window emphasizes the broad trend."
            ),
        },
        {
            "title": "Check the rating distribution",
            "targets": ("tabs",),
            "tab": ("tabs", 1),
            "body": (
                "Ratings divides results into General, Sensitive, Questionable, "
                "and Explicit. Use it to verify that the main search's rating "
                "filters produced the mix you expected."
            ),
        },
        {
            "title": "Explore tag-category rankings",
            "targets": ("tabs",),
            "tab": ("tabs", 4),
            "body": (
                "Characters, Copyrights, Artists, and General Tags rank common "
                "values. Count is the number of matching posts; percentage is "
                "coverage within these results, not the full database."
            ),
        },
        {
            "title": "Use exact values and compare searches",
            "targets": ("date_table",),
            "tab": ("tabs", 0),
            "body": (
                "The table below the chart contains exact values for every time "
                "bucket. Close the dashboard, alter the main query, and reopen it "
                "to compare another population. Analytics never changes search data."
            ),
        },
    ],
}

TUTORIAL["more_info"] = (
    "Analytics is a read-only view of the current result set. It collects only "
    "the columns needed by each tab, so changing a chart option does not alter "
    "the main query or download additional posts."
)

_MORE_INFO = {
    "What this dashboard analyzes": "The post count in the dashboard header is the denominator used for percentages. If that count is unexpected, close Analytics and check the main query, ratings, dates, and thresholds first.",
    "Choose the date resolution and chart": "Resolution changes time buckets, not source data. Day buckets can be sparse; Month is usually the best balance; Year is ideal when comparing the whole archive.",
    "Compare percentages or absolute volume": "Normalization is especially useful across years because total Danbooru upload volume changes over time. Raw counts are better for workload estimates and absolute popularity.",
    "Smooth short-term noise": "A seven-period window means seven days, months, or years depending on the selected interval. Smoothing affects the drawn series only; the exact-value table stays available for verification.",
    "Check the rating distribution": "Rating percentages should add to approximately 100% after rounding. A missing category usually means its main-window checkbox was disabled or no matching posts exist.",
    "Explore tag-category rankings": "Coverage can exceed intuitive category totals because one post can contain many tags. Use high-coverage tags to identify dominant subjects and low-coverage tags for niche branches.",
    "Use exact values and compare searches": "For a controlled comparison, change only one main-search condition between runs. This makes it easier to attribute a chart or ranking difference to that specific filter.",
}
for _step in TUTORIAL["steps"]:
    _step["more_info"] = _MORE_INFO[_step["title"]]
