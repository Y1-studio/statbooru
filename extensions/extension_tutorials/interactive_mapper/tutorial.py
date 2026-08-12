"""Detailed in-dialog tutorial for Interactive Tag Mapper."""

TUTORIAL = {
    "id": "interactive_mapper",
    "order": 40,
    "name": "Interactive Tag Mapper",
    "matches": ("interactive tag mapper",),
    "window_matches": ("interactive tag mapper",),
    "summary": (
        "Explore tag frequency and relationships, then build a main query from "
        "selected tags or export the visible statistics."
    ),
    "steps": [
        {
            "title": "Understand the data source",
            "targets": ("refresh_button",),
            "body": (
                "The mapper uses the current main-window result set, so run a "
                "search first. Refresh rebuilds statistics if those results change. "
                "The extension never scans unrelated posts outside that result set."
            ),
        },
        {
            "title": "Filter the visible tag population",
            "targets": ("search_box", "category_combo", "min_count", "top_n"),
            "body": (
                "Search filters names; Category limits tag type. Min count removes "
                "uncommon tags and Top caps retained rows. Stronger limits make "
                "relationship work faster and reduce visual clutter."
            ),
        },
        {
            "title": "Read and select table rows",
            "targets": ("table",),
            "body": (
                "Each row shows a tag, category, post count, and coverage of the "
                "current results. Select a row to make that tag the focus for "
                "relationship, include, and exclude actions."
            ),
        },
        {
            "title": "Focus on related tags",
            "targets": ("related_button", "only_related"),
            "body": (
                "<b>Map Related</b> rebuilds around the selected tag. Related to "
                "selected limits the table to that neighborhood. Reset to All "
                "returns from relationship focus to the complete visible set."
            ),
        },
        {
            "title": "Use the Bubble Visualizer",
            "targets": ("bubble_button",),
            "body": (
                "Bubble Visualizer opens a network view. Configure focus, node and "
                "edge limits, labels, and layout, then Generate. Node size represents "
                "frequency; edges represent co-occurrence strength."
            ),
        },
        {
            "title": "Build the main query",
            "targets": ("include_button", "exclude_button"),
            "body": (
                "Include adds the selected tag normally to the main query. Exclude "
                "adds its negative form. Use these controls to refine the search "
                "without manually retyping long or unfamiliar tag names."
            ),
        },
        {
            "title": "Reset filters safely",
            "targets": ("reset_button", "clear_filters_button", "refresh_button"),
            "body": (
                "Reset to All removes relationship focus. Clear removes view "
                "filters such as text and category. These actions change only the "
                "mapper view; they do not erase the main search query."
            ),
        },
        {
            "title": "Copy or export findings",
            "targets": ("copy_button", "export_button"),
            "body": (
                "Copy Visible sends filtered tag names to the clipboard. Export "
                "CSV preserves visible counts, categories, and coverage for a "
                "spreadsheet or another analysis tool."
            ),
        },
    ],
}

TUTORIAL["more_info"] = (
    "The mapper turns the current result set into tag-frequency and co-occurrence "
    "views. It is most useful after a focused search; millions of unrelated posts "
    "produce a broad and less meaningful network."
)

_MORE_INFO = {
    "Understand the data source": "Refreshing reads the host application's current DataFrame. It does not rerun the original database search, so run Search in the main window first when filters have changed.",
    "Filter the visible tag population": "Filters are client-side and reversible. Increase Min count before reducing Top when you want to remove weak evidence rather than merely shorten the list.",
    "Read and select table rows": "Coverage is count divided by the number of posts in the current results. A tag with high coverage is representative of the set even when its global Danbooru count is modest.",
    "Focus on related tags": "Relatedness is based on co-occurrence inside the current results. Changing the source query can therefore change relationships even for the same selected tag.",
    "Use the Bubble Visualizer": "Dense networks are easier to read after lowering node count or raising the edge threshold. Structured layout is predictable; force layout can reveal clusters but may move between runs.",
    "Build the main query": "Included tags narrow results by requiring them. Excluded tags remove posts containing them. Review the query text before searching when adding several selections in sequence.",
    "Reset filters safely": "Reset and Clear affect only mapper state. They are useful recovery actions when filters produce an empty table or a relationship focus becomes too narrow.",
    "Copy or export findings": "Copy is convenient for a tag list; CSV is better when counts and coverage must be preserved. Export reflects only currently visible rows and filters.",
}
for _step in TUTORIAL["steps"]:
    _step["more_info"] = _MORE_INFO[_step["title"]]
