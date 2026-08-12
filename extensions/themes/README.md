# Theme files

`theme_switcher.py` is the extension entry point and coordinator. It loads the
theme definitions and private runtime modules in this directory. Because the
host only discovers `extensions/*.py`, these runtime files are not loaded as
standalone extensions.

The numbered JSON filename prefix controls menu order.

## Add or remove themes

Theme discovery is now file-based. Close Statbooru, change the files in this
folder, and start it again:

- Remove a numbered JSON file to remove only that theme from the menu.
- Add a valid numbered JSON file to add a palette-only theme.
- For a theme with custom behavior, keep its matching runtime listed below.
  If that Python runtime is missing or cannot load, only its dependent theme is
  skipped; the Theme extension and all other themes continue to work.
- If the saved active theme was removed, Statbooru selects Midnight Sakura, or
  the first remaining valid theme if Midnight Sakura was also removed.

The shared `stylesheet_renderer.py` file is theme infrastructure, not a
selectable theme, and should remain in this folder. `retro_dither.py` is shared
by the three retro XP themes; removing it removes those three themes and merely
turns off optional image dithering in Windows 3.1 and XP Luna Classic.

## Naming

- Every selectable theme has one `NN_theme_name.json` file.
- The JSON `name` value is the label shown in the Theme menu.
- A matching Python file is needed only when that theme has custom behavior.
- Shared helpers use capability names instead of theme names.

For example, `10_windows_31.json` supplies the Windows 3.1 colors and menu
name, while `windows_31.py` supplies its special readability behavior.
The three Windows XP JSON themes share `retro_dither.py`, so they do not need
three nearly identical Python files. Plain palette themes such as Warm Paper
need no Python runtime at all.

Each file requires a unique `name` plus these palette keys:

- `bg`, `surface`, `surface_alt`
- `border`, `border_hover`
- `text`, `muted`
- `accent`, `accent_hover`, `accent_text`
- `success`

Optional feature flags select the matching runtime:

- `windows_7_aero.py` owns Aero transparency, platform glass, and backing layers.
- `windows_31.py` owns Windows 3.1 readability and autocomplete behavior.
- `windows_xp_luna_classic.py` owns the XP Luna classic-layout behavior.
- `windows_8_metro.py` owns Metro tile colors and button styling.
- `retro_dither.py` owns palettes, textures, emoji/thumbnail/full-image dithering.
- `stylesheet_renderer.py` turns a JSON palette into the shared Qt stylesheet.

Keep behavior used by only one theme in that theme's runtime. The coordinator
should contain only loading, shared settings, lifecycle hooks, and dispatch.
