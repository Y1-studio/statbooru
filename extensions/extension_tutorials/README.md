# Extension tutorials

Each supported extension has one folder containing a `tutorial.py` file:

```text
extension_tutorials/
├── analytics/tutorial.py
├── annual_seasonality/tutorial.py
├── compare_tags/tutorial.py
├── interactive_mapper/tutorial.py
├── tag_explosions/tutorial.py
└── theme/tutorial.py
```

The `mascot/` folder contains the transparent helper artwork. `RMQ2.png` is
the pointing pose used for control topics, while `RMQ2_1.png` is the neutral
pose used for the first page of a tutorial.

`tutorial_state.json` stores the welcome tutorial's completed version. This
portable file replaces `QSettings`, so the tutorial does not use the Windows
Registry. Delete the file or set its version to `0` to trigger the welcome
tutorial on the next launch.

`welcome_tutorial.py` discovers every `tutorial.py` recursively. Each file
exports one `TUTORIAL` dictionary with:

- `id`: stable unique identifier.
- `order`: ordering in the full welcome tour.
- `name`: user-facing extension name.
- `matches`: fragments matching the main-window extension button.
- `window_matches`: fragments matching the extension dialog title.
- `summary`: concise description used by the main welcome tour.
- `steps`: ordered detailed pages for the in-extension tutorial.

Each step contains `title`, HTML-capable `body`, HTML-capable `more_info`, and
`targets`, an ordered tuple of dialog attribute names. Available targets are
highlighted. The `more_info` content appears in the mascot speech bubble. A step
may also specify `tab: ("tab_widget_attribute", index)`; the loader switches to
that tab before highlighting. Controls inside a scroll area are brought into
view automatically.

Dataset Updater intentionally has no tutorial module.
