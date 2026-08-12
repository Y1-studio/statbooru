"""Detailed in-dialog tutorial for Compare Tags Globally."""

TUTORIAL = {
    "id": "compare_tags",
    "order": 20,
    "name": "Compare Tags Globally",
    "matches": ("compare tags globally",),
    "window_matches": ("compare tags over time",),
    "summary": (
        "Compare multiple advanced tag queries across a configurable historical "
        "range using raw or normalized trends."
    ),
    "steps": [
        {
            "title": "Choose a meaningful date range",
            "targets": ("date_from_edit", "date_to_edit"),
            "body": (
                "The active range defines the dataset history being compared. "
                "Short ranges process faster and work well by Day or Month. For "
                "the complete archive, Month or Year usually produces a clearer chart."
            ),
        },
        {
            "title": "Select the time interval",
            "targets": ("combo_interval",),
            "body": (
                "Year provides a compact long-term comparison, Month reveals "
                "seasonality, and Day exposes event-sized spikes. Very fine "
                "intervals over broad ranges create many points and take longer."
            ),
        },
        {
            "title": "Choose counts or normalized share",
            "targets": ("chk_normalize",),
            "body": (
                "Raw counts answer “how many posts used this query?” Normalize "
                "answers “what percentage of all posts used it?” Normalization "
                "reduces the visual effect of Danbooru's overall growth."
            ),
        },
        {
            "title": "Control smoothing",
            "targets": ("chk_smooth", "spin_smooth"),
            "body": (
                "Smoothing averages neighboring time buckets. A small window "
                "softens noise while retaining events; a larger window reveals "
                "broad direction. Disable it when exact spikes are important."
            ),
        },
        {
            "title": "Build comparable query groups",
            "targets": ("btn_add_group",),
            "body": (
                "Enter one query per colored group. Groups accept the main search "
                "syntax, including multiple tags, exclusions, ratings, wildcards, "
                "and OR expressions. Add or remove groups as your comparison changes."
            ),
        },
        {
            "title": "Generate the chart",
            "targets": ("btn_generate",),
            "body": (
                "Click <b>Generate Chart</b>. The first run may take longer while "
                "global totals are calculated; reusable totals are cached. The "
                "status line reports calculation progress and invalid queries."
            ),
        },
        {
            "title": "Interpret and refine the comparison",
            "targets": ("btn_generate",),
            "body": (
                "Line direction shows growth or decline; distance between series "
                "shows relative size. If one popular tag flattens the others, turn "
                "on normalization or compare it separately, then generate again."
            ),
        },
    ],
}

TUTORIAL["more_info"] = (
    "Compare Tags evaluates each group against the same historical database and "
    "date buckets. It is intended for relative trend analysis rather than editing "
    "the current main-window results."
)

_MORE_INFO = {
    "Choose a meaningful date range": "Use matching start and end dates when reproducing a comparison later. Extremely short ranges may contain too few posts, while very broad daily ranges create thousands of buckets.",
    "Select the time interval": "The interval should match the question: Day for releases or events, Month for seasonal behavior, and Year for long-term adoption or decline.",
    "Choose counts or normalized share": "A tag may gain raw posts while losing share if the site grows faster than the tag. Looking at both modes distinguishes absolute growth from relative popularity.",
    "Control smoothing": "Smoothing can shift or soften peaks, so turn it off before reporting an exact peak date. Keep the same window for every group in a comparison.",
    "Build comparable query groups": "Groups are full queries, not just single tags. You can compare character_a rating:g against character_a rating:e, or two franchises with the same exclusions.",
    "Generate the chart": "Unchanged date and interval settings allow cached global totals to be reused. Editing a group usually costs less than changing the complete time range.",
    "Interpret and refine the comparison": "Crossing lines indicate a change in relative ordering. Confirm apparent crossovers without smoothing and inspect neighboring buckets before drawing conclusions.",
}
for _step in TUTORIAL["steps"]:
    _step["more_info"] = _MORE_INFO[_step["title"]]
