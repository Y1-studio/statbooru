# Danbooru Dataset Finder Extended

A high-speed desktop tool for searching, filtering, analyzing, and exporting Danbooru metadata for AI training dataset curation.

This project is based on [`ThetaCursed/Danbooru-Dataset-Filter`](https://github.com/ThetaCursed/Danbooru-Dataset-Filter) and keeps the same core idea: a fast local Danbooru metadata explorer powered by **Polars**, **Apache Parquet**, and **PyQt6**. This extended version adds a plugin system, richer Danbooru-style query syntax, memory-safe processing modes, thumbnail previews, and multiple analysis extensions for tag research.

> Designed for LoRA, checkpoint, Flux/SDXL/Anima, ControlNet, and general computer-vision dataset curation workflows.

---

## Why this exists

The original Danbooru Dataset Filter is great for quickly filtering millions of Danbooru records by tags, score, favorites, rating, orientation, and date. This version turns that workflow into a larger research dashboard for people who need to explore **tag relationships**, **tag growth**, **dataset trends**, and **query performance** before exporting image URLs.

---

## Key features

- **Fast local search** over Danbooru Parquet metadata with Polars lazy queries.
- **Unified Danbooru-style query box** supporting tags, negation, `OR`, wildcards, metadata filters, source filters, Pixiv filters, and order modifiers.
- **Rating, date, score, favorites, orientation, and MD5 dedup filters** from the GUI.
- **Two search modes**:
  - Fast in-process search for normal usage.
  - Memory-safe isolated search for huge queries that should release temporary native memory after completion.
- **Optional thumbnail preview** using Danbooru CDN thumbnail URLs.
- **Extension loader** that automatically loads Python plugins from `./extensions/`.
- **Export image URLs to TXT** for downstream downloaders or training pipelines.
- **Dark Catppuccin-style UI** optimized for long curation sessions.

---

## What changed from `ThetaCursed/Danbooru-Dataset-Filter`?

| Area | Upstream project | This extended version |
|---|---|---|
| Core purpose | Fast GUI metadata filtering and URL export | Same core filtering workflow, plus analysis and research tooling |
| Query input | Include/exclude style filtering | Unified Danbooru-style query box with `OR`, negation, wildcards, `source:`, `pixiv:`, numeric ranges, and `order:` syntax |
| Data loading | Main local Parquet database | Combines local clean metadata and optional API-synced metadata when available |
| Memory behavior | Fast local Polars search | Adds a memory-safe isolated search mode for very large queries |
| Extensions | Not the main focus | Built-in extension API using `setup(app)` / `register(app)`, extension buttons, `get_current_df()`, and `data_updated` |
| Visual preview | Table preview and tags | Optional CDN thumbnails, colored tags, clickable tag preview, and image viewing workflow |
| Analytics | Basic curation workflow | Tag analytics dashboard, global tag comparison charts, related-tag mapping, bubble visualization, and tag-growth discovery |
| Tag discovery | Manual query exploration | Low-RAM normalized tag explosion finder with baseline/recent windows and tag-type filters |
| Research workflow | Find and export a dataset | Explore trends, compare tags over time, inspect related tags, then export URLs |

---

## Query examples

```text
1girl score:>50 rating:g,s order:score
hatsune_miku OR megurine_luka -lowres favcount:>=25
*miku* source:*pixiv* order:favcount
pixiv:any width:>=1024 height:>=1024 rating:e
score:100..500 date order:random
```

Supported query concepts include:

- Exact tags: `1girl`, `solo`, `blue_archive`
- Negative tags: `-lowres`, `-bad_id`
- Simple OR: `hatsune_miku OR megurine_luka`
- Wildcards: `*miku*`
- Numeric metadata: `score:>50`, `favcount:10..200`, `width:>=1024`, `height:<2048`, `id:123456`
- Ratings: `rating:g`, `rating:s`, `rating:q`, `rating:e`, or comma groups like `rating:g,s`
- Source matching: `source:none`, `source:http`, `source:*pixiv*`
- Pixiv matching: `pixiv:any`, `pixiv:123456`, `pixiv:1000..9999`
- Sorting from the query: `order:score`, `order:favcount`, `order:date`, `order:id`, `order:random`

---

## Extensions included

Place extension files in the `extensions/` folder. The app loads every `.py` file with a `setup(app)` or `register(app)` entry point.

### 📊 Tag Analytics

A dashboard for analyzing the current filtered dataset:

- Date distribution by year, month, or day.
- Rating distribution.
- Top character, copyright, artist, and general tags.
- Optional normalization and smoothing for date charts.

### 📈 Compare Tags Globally

Compare multiple tag queries over time:

- Supports year/month/day grouping.
- Uses the same advanced query parser when available.
- Can normalize tag counts against total posts for the selected period.
- Caches chart data so repeated comparisons are faster.

### 💥 Low-RAM Tag Explosions

Find tags that are growing unusually fast between two date windows:

- Streams Parquet batches with PyArrow instead of loading everything into RAM.
- Compares a baseline window against a recent/explosion window.
- Scores tags by normalized growth, recent count, and percentage delta.
- Supports tag-type filters: artist, copyright, character, general, and meta.
- Supports seed tags, exclusion lists, only-new tags, exclude-new tags, and artist-dominance filtering.

### 🧭 Interactive Tag Mapper + Bubble Visualizer

Explore tag relationships inside the current search result:

- Counts tag coverage by category.
- Maps related tags from a selected tag.
- Opens an interactive bubble graph of co-occurring tags.
- Includes category legend, search highlighting, edge-strength controls, zoom controls, context menus, CSV export, and clipboard helpers.

---

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/YOUR_USERNAME/YOUR_REPO_NAME.git
cd YOUR_REPO_NAME
```

### 2. Create a virtual environment

```bash
python -m venv .venv
```

Activate it:

```bash
# Windows
.venv\Scripts\activate

# Linux / macOS
source .venv/bin/activate
```

### 3. Install dependencies

```bash
pip install polars pyarrow PyQt6 requests matplotlib
```

Optional but recommended for a repo release:

```bash
pip freeze > requirements.txt
```

### 4. Add the metadata files

Create a `data/` folder next to `main.py`:

```text
project-root/
├── data/
│   ├── danbooru2026_clean.parquet
│   ├── tags_dictionary.parquet
│   ├── danbooru_api_clean.parquet          # optional
│   └── tags_dictionary_API.parquet         # optional
├── extensions/
├── main.py
└── README.md
```

The base upstream project points users to the Danbooru 2026 clean metadata files on Hugging Face. This extended app expects the same style of local Parquet metadata and tag dictionary files.

Do **not** commit large `.parquet` files to GitHub. Keep them in `data/` locally and add them to `.gitignore`.

### 5. Install extensions

Recommended file names:

```text
extensions/
├── analytics.py
├── tag_compare.py
├── tag_explosion_finder.py
└── interactive_tag_mapper_extension_v9.py
```

If your files were downloaded with names like `analytics(2).py` or `tag_compare(1).py`, rename them before committing.

### 6. Run the app

```bash
python main.py
```

---

## Recommended `.gitignore`

```gitignore
.venv/
__pycache__/
*.pyc
.DS_Store

# Local Danbooru metadata/cache files
data/*.parquet
data/*.csv
data/*.txt

# Exported datasets
exports/
*.log
```

---

## Usage workflow

1. Start the app with `python main.py`.
2. Enter a query such as `1girl score:>50 rating:g,s order:favcount`.
3. Adjust score/favorite thresholds, rating, orientation, deduplication, and date filters.
4. Choose **Fast in-process** for speed or **Memory-safe isolated** for massive searches.
5. Run the search.
6. Use the extensions to analyze results:
   - Open **Tag Analytics** for distribution summaries.
   - Open **Compare Tags Globally** to chart tag trends.
   - Open **Low-RAM Tag Explosions** to discover rising tags.
   - Open **Interactive Tag Mapper** to inspect related tags and co-occurrence clusters.
7. Export image URLs to `.txt` when the dataset looks right.

---

## Project structure

```text
project-root/
├── main.py
├── README.md
├── extensions/
│   ├── analytics.py
│   ├── tag_compare.py
│   ├── tag_explosion_finder.py
│   └── interactive_tag_mapper_extension_v9.py
└── data/
    ├── danbooru2026_clean.parquet
    ├── tags_dictionary.parquet
    ├── danbooru_api_clean.parquet
    └── tags_dictionary_API.parquet
```

---

## Extension API notes

Extensions can integrate with the host app through:

```python
def setup(app):
    # create buttons, dialogs, and hooks here
    ...
```

Useful host methods/signals:

- `app.add_extension_button(button)` — add a button to the main extension button row.
- `app.get_current_df()` — access the current filtered Polars DataFrame.
- `app.get_results_df()` — compatibility alias for `get_current_df()`.
- `app.get_unlimited_lazy_df()` — access a lazy pipeline when available.
- `app.data_updated` — react when the active search result changes.

---

## Notes and limitations

- This tool works on local metadata. It does not download full images by itself unless you use the exported URLs with an external downloader.
- Thumbnail preview requires network access to the Danbooru CDN.
- Very large searches can temporarily use significant RAM. Use **Memory-safe isolated** mode when working with huge result sets.
- The app assumes Danbooru-style metadata columns such as `id`, `rating`, `score`, `fav_count`, `file_url`, `created_at`, `md5`, and tag category columns.

---

## Credits

Based on [`ThetaCursed/Danbooru-Dataset-Filter`](https://github.com/ThetaCursed/Danbooru-Dataset-Filter), a fast Polars/PyQt6 GUI for curating Danbooru image datasets.

This extended version adds plugin-based analytics, richer query parsing, memory-focused processing, and tag research tools on top of the original concept.

