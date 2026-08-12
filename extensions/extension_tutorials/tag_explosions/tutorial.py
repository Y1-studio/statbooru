"""Detailed in-dialog tutorial for Low-RAM Tag Explosions."""

TUTORIAL = {
    "id": "tag_explosions",
    "order": 50,
    "name": "Low-RAM Tag Explosions",
    "matches": ("tag explosions",),
    "window_matches": ("tag explosion finder",),
    "summary": (
        "Find tags whose normalized usage rose sharply between a baseline and "
        "recent period without loading the whole dataset into RAM."
    ),
    "steps": [
        {
            "title": "Choose comparable time windows",
            "targets": (
                "date_baseline_from", "date_baseline_to",
                "date_recent_from", "date_recent_to", "btn_link_windows",
            ),
            "body": (
                "Baseline represents normal historical usage; Explosion is the "
                "later period being tested. Similar-duration windows make growth "
                "ratios easier to interpret. The link control helps align durations."
            ),
        },
        {
            "title": "Set confidence thresholds",
            "targets": ("spin_min_recent", "spin_growth", "spin_limit"),
            "body": (
                "Min recent posts removes tiny samples. Min growth sets the "
                "required multiplication over baseline. Limit caps output size. "
                "Stricter values produce fewer, more confident discoveries."
            ),
        },
        {
            "title": "Select tag categories",
            "targets": (
                "chk_artist", "chk_copyright", "chk_character",
                "chk_general", "chk_meta", "btn_all_types", "btn_no_types",
            ),
            "body": (
                "Choose Artist, Copyright, Character, General, and/or Meta. All "
                "and None are quick selectors. Fewer categories reduce scan time "
                "and make the result table more focused."
            ),
        },
        {
            "title": "Use seed tags to define scope",
            "targets": ("input_seed", "chk_use_current_include"),
            "body": (
                "Optional seeds restrict analysis to matching posts, such as one "
                "franchise. You can also use current Include tags as seeds. Leave "
                "the field empty for a global discovery scan."
            ),
        },
        {
            "title": "Remove known or misleading growth",
            "targets": (
                "chk_hide_current", "chk_only_new", "chk_exclude_new",
                "chk_artist_dom",
            ),
            "body": (
                "Hide current tags removes items already in the main query. Only "
                "zero-baseline finds genuinely new tags; Exclude new does the "
                "opposite. Artist-dominance filters remove one-artist distortions."
            ),
        },
        {
            "title": "Balance memory, speed, and compatibility",
            "targets": ("spin_batch", "spin_workers", "combo_count_mode"),
            "body": (
                "Larger batches and more workers can run faster but consume more "
                "RAM. Category columns are normally the efficient Count Mode; "
                "tag_string is a compatibility fallback. Start conservatively."
            ),
        },
        {
            "title": "Run and interpret the scan",
            "targets": ("btn_analyze", "status", "table"),
            "body": (
                "Click Find Normalized Exploding Tags and watch Status. Compare "
                "baseline count, recent count, normalized growth, and supporting "
                "metrics—high growth with adequate recent volume is most useful."
            ),
        },
        {
            "title": "Use discoveries and manage cache",
            "targets": (
                "btn_include", "btn_exclude", "btn_search",
                "btn_open_danbooru", "btn_copy", "btn_clear_cache",
            ),
            "body": (
                "Select a result to include/exclude it, show it in the main window, "
                "open Danbooru, or copy its name. Clear Cache only when inputs have "
                "changed or you need counts rebuilt from source data."
            ),
        },
    ],
}

TUTORIAL["more_info"] = (
    "Tag Explosions compares normalized usage between two periods. It is designed "
    "to find emerging subjects while streaming data in batches so peak memory use "
    "stays controllable."
)

_MORE_INFO = {
    "Choose comparable time windows": "Equal-duration windows simplify interpretation. Avoid overlapping windows, and consider seasonal bias—for example, compare the same months when annual events could dominate.",
    "Set confidence thresholds": "A huge multiplier from one baseline post to five recent posts is usually weak evidence. Min recent posts protects against these mathematically large but practically tiny changes.",
    "Select tag categories": "Category choice changes the candidate universe. Artist explosions often reflect contributor activity, while Character or Copyright explosions more often reflect releases and events.",
    "Use seed tags to define scope": "Seeds are applied before counting candidate tags. A franchise seed asks which tags are exploding within that franchise, not whether the franchise itself is exploding globally.",
    "Remove known or misleading growth": "Zero-baseline tags need special handling because their growth ratio is effectively unbounded. Artist dominance can identify a trend caused by one uploader or creator rather than broad adoption.",
    "Balance memory, speed, and compatibility": "If the system becomes unresponsive, reduce workers first, then batch size. Faster storage benefits more from parallel work than a slow or heavily used drive.",
    "Run and interpret the scan": "Prioritize tags supported by both a strong normalized multiplier and substantial recent volume. Inspect the baseline/recent dates before comparing two saved runs.",
    "Use discoveries and manage cache": "Cache reuse is safe only when the relevant source files and calculation settings are unchanged. Clearing it discards derived counts, not the original dataset.",
}
for _step in TUTORIAL["steps"]:
    _step["more_info"] = _MORE_INFO[_step["title"]]
