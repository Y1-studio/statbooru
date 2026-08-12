"""Detailed in-dialog tutorial for Themes and Display Settings."""

TUTORIAL = {
    "id": "theme",
    "order": 60,
    "name": "Themes and Display Settings",
    "matches": ("theme",),
    "window_matches": ("choose theme",),
    "summary": (
        "Preview visual themes and configure dithering, image resolution, native "
        "effects, and extension-window styling."
    ),
    "steps": [
        {
            "title": "Preview and save a theme",
            "targets": ("theme_combo",),
            "body": (
                "Selecting a theme previews it immediately across the application "
                "and this tutorial. The selected name is saved automatically, so "
                "it becomes the starting appearance on the next launch."
            ),
        },
        {
            "title": "Understand the theme families",
            "targets": ("theme_combo",),
            "body": (
                "Modern themes mainly change colors. Windows XP, Windows 8, and "
                "Windows 3.1 also change control geometry. Dithered themes transform "
                "visual assets; Windows 7 Aero can use native glass effects."
            ),
        },
        {
            "title": "Configure color-map dithering",
            "targets": ("enable_dither", "color_count_slider"),
            "body": (
                "Supported retro themes can reduce icons and images to a limited "
                "palette. Fewer colors create a stronger period look; more colors "
                "preserve detail. Unsupported themes disable these controls."
            ),
        },
        {
            "title": "Choose where dithering applies",
            "targets": ("dither_thumbnails", "apply_dither_button"),
            "body": (
                "Choose whether result thumbnails and separately opened pictures "
                "are transformed. Click Apply Dither Settings after changing these "
                "options or the color count."
            ),
        },
        {
            "title": "Balance full-image quality and speed",
            "targets": ("full_image_resolution",),
            "body": (
                "Maximum resolution caps the longest image edge before dithering. "
                "Lower values process faster and use less memory. Unlimited retains "
                "source resolution but may be expensive for very large images."
            ),
        },
        {
            "title": "Style extension windows consistently",
            "targets": ("force_theme",),
            "body": (
                "Force Theme applies selected colors to extension dialogs, charts, "
                "and controls that otherwise use custom colors. It refreshes those "
                "windows periodically; tutorial controls retain safe contrast."
            ),
        },
        {
            "title": "Apply display settings and close",
            "targets": ("apply_display_button",),
            "body": (
                "Click Apply Display Settings after changing resolution or Force "
                "Theme. Theme-specific native controls may appear below. Closing "
                "this dialog never changes your query, dataset, or results."
            ),
        },
    ],
}

TUTORIAL["more_info"] = (
    "Themes combine color tokens, Qt styles, and optional runtime effects. Search "
    "data is unaffected; only rendering, image transformation, and extension-window "
    "styling change."
)

_MORE_INFO = {
    "Preview and save a theme": "Preview is live, so open representative controls before deciding. The chosen theme name is stored in QSettings rather than written into the dataset or source files.",
    "Understand the theme families": "Retro themes intentionally use sharper edges, limited palettes, and period typography. Modern themes favor smoother surfaces and may depend on platform compositing for effects.",
    "Configure color-map dithering": "Dithering simulates unavailable colors by alternating available pixels. It can add texture and apparent detail, but very low color counts may obscure small icons.",
    "Choose where dithering applies": "Thumbnail and picture options are separate because full images cost more to transform. Disable opened-picture dithering when inspecting original colors is important.",
    "Balance full-image quality and speed": "The resolution limit affects processing input, while the viewer can still scale the transformed result. A moderate cap is usually visually sufficient for on-screen viewing.",
    "Style extension windows consistently": "Force Theme periodically corrects hard-coded extension colors and chart palettes. Tutorial widgets opt out only where necessary to preserve speech-bubble and navigation contrast.",
    "Apply display settings and close": "Apply is required for resolution and Force Theme changes; simple theme selection is saved immediately. If an extension is already open, close and reopen it if a custom control does not refresh.",
}
for _step in TUTORIAL["steps"]:
    _step["more_info"] = _MORE_INFO[_step["title"]]
