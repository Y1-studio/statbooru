"""
Low-RAM Normalized Tag Explosion Finder for Danbooru Dataset Finder.

Install:
    Save as:
        extensions/tag_explosion_finder.py

Features:
    - Low RAM: streams filtered parquet batches.
    - Date filtering is pushed into PyArrow's dataset scanner.
    - Normalized growth scoring.
    - Tag type selection: artist / copyright / character / general / meta.
    - Optional seed tags.
    - Exclude new tags option: removes zero-baseline tags from results.
    - Explicit Baseline (Normalize) and Explosion (Recent) date windows,
      kept contiguous: baseline_to + 1 day == recent_from.
"""

import os
import re
import math
import webbrowser
from urllib.parse import quote
from collections import Counter, deque
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, date

try:
    import pyarrow as pa
    import pyarrow.dataset as ds
    import pyarrow.types as patypes
except Exception:
    pa = None
    ds = None
    patypes = None

from PyQt6.QtCore import Qt, QThread, pyqtSignal, QDate
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QCheckBox,
    QComboBox,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QMessageBox,
    QApplication,
    QGroupBox,
    QLineEdit,
    QDateEdit,
    QToolButton,
)


TAG_COLUMNS = [
    ("tag_string_artist", "artist", "#f38ba8"),
    ("tag_string_copyright", "copyright", "#cba6f7"),
    ("tag_string_character", "character", "#a6e3a1"),
    ("tag_string_general", "general", "#89b4fa"),
    ("tag_string_meta", "meta", "#fab387"),
]

DEFAULT_COLOR = "#cdd6f4"


def _parse_tags(text):
    if not text:
        return []
    return [t.strip().lower() for t in re.split(r"[,\n ]+", text) if t.strip()]


def _split_tag_string(text):
    if not text:
        return []
    return str(text).split()


def _date_unit(date_text, interval):
    if not date_text:
        return None
    s = str(date_text)
    if interval == "Year":
        return s[:4] if len(s) >= 4 else None
    if interval == "Month":
        return s[:7] if len(s) >= 7 else None
    return s[:10] if len(s) >= 10 else None


def _date_iso(date_text):
    """Return the YYYY-MM-DD prefix of any created_at value, or None."""
    if not date_text:
        return None
    s = str(date_text)
    return s[:10] if len(s) >= 10 else None


def _qdate_to_iso(qdate):
    return qdate.toString("yyyy-MM-dd")


def _date_scalar_for_arrow(date_text, arrow_type):
    """Build a scalar compatible with created_at's Arrow type."""
    y, m, d = [int(x) for x in str(date_text)[:10].split("-")]

    if patypes.is_date32(arrow_type) or patypes.is_date64(arrow_type):
        return pa.scalar(date(y, m, d), type=arrow_type)

    if patypes.is_timestamp(arrow_type):
        return pa.scalar(datetime(y, m, d), type=arrow_type)

    return pa.scalar(str(date_text)[:10])


def score_explosions(
    *,
    recent_counts,
    baseline_counts,
    category_vote,
    color_vote,
    total_recent,
    total_baseline,
    settings,
    scanned_rows,
    matched_seed,
    cached,
    recent_artist_counts=None,
    artist_tag_set=None,
):
    """Turn raw per-tag counts into ranked explosion rows.

    All filters here are CHEAP (no parquet I/O), so this is what we re-run
    when only the exclude list, thresholds, or new-tag toggles change.
    """
    selected_types = settings.get("selected_types") or []
    type_label = ", ".join(selected_types) if selected_types else "(all)"

    excluded_tags = set(settings.get("excluded_tags") or [])
    min_recent = settings["min_recent"]
    min_growth = settings["min_growth"]
    limit_tags = settings["limit_tags"]
    only_new = settings["only_new"]
    exclude_new = settings.get("exclude_new", False)

    artist_dominance_enabled = bool(settings.get("artist_dominance_enabled"))
    # Threshold is a percentage 1-100. A tag is dropped if any single artist
    # accounts for >= threshold% of its solo-artist recent posts.
    artist_dominance_threshold_pct = float(settings.get("artist_dominance_threshold", 70))
    # Don't trigger the filter unless there are enough solo-artist posts to be meaningful.
    artist_dominance_min_solo = int(settings.get("artist_dominance_min_solo", 5))

    if artist_tag_set is None:
        artist_tag_set = set()

    baseline_from = settings["baseline_from"]
    baseline_to = settings["baseline_to"]
    recent_from = settings["recent_from"]
    recent_to = settings["recent_to"]
    batch_size = settings["batch_size"]

    dominance_dropped = 0

    rows = []
    for tag, recent_count in recent_counts.items():
        if tag in excluded_tags:
            continue
        if recent_count < min_recent:
            continue

        baseline_count = baseline_counts.get(tag, 0)
        recent_pct = recent_count / total_recent * 100.0
        baseline_pct = baseline_count / total_baseline * 100.0

        if only_new:
            if baseline_count != 0:
                continue
            growth_x = 999999.0
        else:
            if exclude_new and baseline_count == 0:
                continue
            growth_x = (recent_pct + 0.000001) / (baseline_pct + 0.000001)
            if growth_x < min_growth:
                continue

        # Artist-dominance filter — does NOT apply to artist tags themselves.
        top_artist = None
        top_artist_share = 0.0
        if artist_dominance_enabled and recent_artist_counts is not None and tag not in artist_tag_set:
            bucket = recent_artist_counts.get(tag)
            if bucket:
                solo_total = sum(bucket.values())
                if solo_total >= artist_dominance_min_solo:
                    top_artist, top_count = bucket.most_common(1)[0]
                    top_artist_share = top_count / solo_total * 100.0
                    if top_artist_share >= artist_dominance_threshold_pct:
                        dominance_dropped += 1
                        continue

        delta_pct = recent_pct - baseline_pct

        score = (
            math.log1p(growth_x) * 45.0
            + math.log1p(recent_count) * 12.0
            + max(0.0, delta_pct) * 120.0
        )

        if baseline_count == 0:
            why = f"New in explosion window: {recent_count:,} posts, {recent_pct:.5f}% of recent posts."
        else:
            why = (
                f"Normalized share rose from {baseline_pct:.5f}% to {recent_pct:.5f}% "
                f"({growth_x:.2f}×)."
            )

        if top_artist and top_artist_share > 0:
            why += f" Top artist '{top_artist}' = {top_artist_share:.1f}% of recent solo posts."

        category = category_vote.get(tag, "unknown")
        color = color_vote.get(tag, DEFAULT_COLOR)

        rows.append({
            "tag": tag,
            "category": category,
            "color": color,
            "recent_count": int(recent_count),
            "baseline_count": int(baseline_count),
            "recent_pct": float(recent_pct),
            "baseline_pct": float(baseline_pct),
            "growth_x": float(growth_x),
            "delta_pct": float(delta_pct),
            "score": float(score),
            "why": why,
        })

    rows.sort(key=lambda r: r["score"], reverse=True)
    rows = rows[:limit_tags]

    cache_marker = " (cached counts)" if cached else ""
    dom_marker = (
        f" Filtered out {dominance_dropped:,} tag(s) dominated by a single artist (≥{artist_dominance_threshold_pct:g}%)."
        if artist_dominance_enabled and dominance_dropped
        else ""
    )
    status = (
        f"Found {len(rows):,} normalized exploding tags for type(s): {type_label}{cache_marker}.{dom_marker} "
        f"Rows scanned in window: {scanned_rows:,}. "
        f"Seed-matched rows: {matched_seed:,}. "
        f"Baseline: {baseline_from} → {baseline_to} ({total_baseline:,} posts). "
        f"Explosion: {recent_from} → {recent_to} ({total_recent:,} posts). "
        f"Batch size: {batch_size:,}."
    )
    return rows, status


def _process_batch(batch_pydict, params):
    """Pure function: turn one batch's pydict into partial counters.

    No I/O, no shared state, safe to call from any thread. Returns a dict with
    the same shape as _count_in_windows's accumulators (just for this batch).
    `params` is a dict of pre-computed scan parameters; building it once in
    the caller saves repeated dict lookups.
    """
    seed_tags = params["seed_tags"]
    seed_tags_set = params["seed_tags_set"]
    skip_tags = params["skip_tags"]
    count_mode = params["count_mode"]
    selected_cols = params["selected_cols"]
    track_artists = params["track_artists"]
    baseline_from = params["baseline_from"]
    baseline_to = params["baseline_to"]
    recent_from = params["recent_from"]
    recent_to = params["recent_to"]

    recent_counts = Counter()
    baseline_counts = Counter()
    category_vote = {}
    color_vote = {}
    recent_artist_counts = {} if track_artists else None
    artist_tag_set = set()

    total_recent = 0
    total_baseline = 0
    scanned = 0
    matched_seed = 0

    created_at_col = batch_pydict.get("created_at") or []
    tag_string_col = batch_pydict.get("tag_string") or []
    artist_col = batch_pydict.get("tag_string_artist") if track_artists else None

    n = len(created_at_col)
    scanned = n

    for i in range(n):
        ca = created_at_col[i]
        if ca is None:
            continue
        ca_str = str(ca)
        iso = ca_str[:10] if len(ca_str) >= 10 else None
        if iso is None:
            continue

        # Window classification (string compare == date order for YYYY-MM-DD).
        if recent_from <= iso <= recent_to:
            in_recent = True
        elif baseline_from <= iso <= baseline_to:
            in_recent = False
        else:
            continue

        tag_string = tag_string_col[i] if i < len(tag_string_col) else None
        tag_string = tag_string or ""

        # Seed-tag gate.
        if seed_tags:
            row_tags = set(tag_string.split())
            if not seed_tags_set.issubset(row_tags):
                continue

        matched_seed += 1
        if in_recent:
            total_recent += 1
        else:
            total_baseline += 1

        # Collect tags from selected category columns.
        selected_type_tags = []
        for col, category, color in selected_cols:
            col_data = batch_pydict.get(col)
            if not col_data:
                continue
            cell = col_data[i]
            if not cell:
                continue
            for tag in str(cell).split():
                selected_type_tags.append(tag)
                if tag not in category_vote:
                    category_vote[tag] = category
                    color_vote[tag] = color
                    if category == "artist":
                        artist_tag_set.add(tag)

        if count_mode == "tag_string":
            allowed = set(selected_type_tags)
            count_tags = [t for t in tag_string.split() if t in allowed]
        else:
            count_tags = selected_type_tags

        # Solo-artist for dominance (recent only).
        solo_artist = None
        if track_artists and in_recent and artist_col is not None:
            artist_cell = artist_col[i] if i < len(artist_col) else None
            if artist_cell:
                row_artists = str(artist_cell).split()
                if len(row_artists) == 1:
                    solo_artist = row_artists[0]

        seen = set()
        for tag in count_tags:
            if not tag or tag in seen:
                continue
            seen.add(tag)
            if tag in skip_tags:
                continue
            if in_recent:
                recent_counts[tag] += 1
                if solo_artist is not None:
                    bucket = recent_artist_counts.get(tag)
                    if bucket is None:
                        bucket = Counter()
                        recent_artist_counts[tag] = bucket
                    bucket[solo_artist] += 1
            else:
                baseline_counts[tag] += 1

    return {
        "recent_counts": recent_counts,
        "baseline_counts": baseline_counts,
        "category_vote": category_vote,
        "color_vote": color_vote,
        "artist_tag_set": artist_tag_set,
        "recent_artist_counts": recent_artist_counts,
        "total_recent": total_recent,
        "total_baseline": total_baseline,
        "scanned": scanned,
        "matched_seed": matched_seed,
    }


def _merge_partial(acc, partial):
    """Fold a per-batch partial into the running accumulators (dict of dicts)."""
    acc["recent_counts"].update(partial["recent_counts"])
    acc["baseline_counts"].update(partial["baseline_counts"])

    cv_acc = acc["category_vote"]
    for t, c in partial["category_vote"].items():
        cv_acc.setdefault(t, c)
    cl_acc = acc["color_vote"]
    for t, color in partial["color_vote"].items():
        cl_acc.setdefault(t, color)

    acc["artist_tag_set"].update(partial["artist_tag_set"])

    if acc["recent_artist_counts"] is not None and partial["recent_artist_counts"] is not None:
        rac = acc["recent_artist_counts"]
        for tag, bucket in partial["recent_artist_counts"].items():
            existing = rac.get(tag)
            if existing is None:
                rac[tag] = Counter(bucket)
            else:
                existing.update(bucket)

    acc["total_recent"] += partial["total_recent"]
    acc["total_baseline"] += partial["total_baseline"]
    acc["scanned"] += partial["scanned"]
    acc["matched_seed"] += partial["matched_seed"]


class NumericTableItem(QTableWidgetItem):
    def __init__(self, display_text, sort_value):
        super().__init__(display_text)
        self.sort_value = sort_value

    def __lt__(self, other):
        if isinstance(other, NumericTableItem):
            return self.sort_value < other.sort_value
        return super().__lt__(other)


class RescoreWorker(QThread):
    """Re-runs score_explosions on cached counts off the GUI thread.

    Emits the same (rows, status, scan_payload) signal shape as the full
    scan worker so the dialog can use one on_success handler for both. We
    pass scan_payload=None on completion because the cache is already
    populated and shouldn't be overwritten.
    """
    progress = pyqtSignal(str)
    finished_ok = pyqtSignal(list, str, object)
    failed = pyqtSignal(str)

    def __init__(self, payload, settings):
        super().__init__()
        self.payload = payload
        self.settings = settings

    def run(self):
        try:
            rows, status = score_explosions(
                recent_counts=self.payload["recent_counts"],
                baseline_counts=self.payload["baseline_counts"],
                category_vote=self.payload["category_vote"],
                color_vote=self.payload["color_vote"],
                total_recent=self.payload["total_recent"],
                total_baseline=self.payload["total_baseline"],
                settings=self.settings,
                scanned_rows=self.payload["scanned_rows"],
                matched_seed=self.payload["matched_seed"],
                cached=True,
                recent_artist_counts=self.payload.get("recent_artist_counts"),
                artist_tag_set=self.payload.get("artist_tag_set"),
            )
            self.finished_ok.emit(rows, status, None)
        except Exception as e:
            import traceback
            traceback.print_exc()
            self.failed.emit(str(e))


class LowRamExplosionWorker(QThread):
    progress = pyqtSignal(str)
    finished_ok = pyqtSignal(list, str, object)
    failed = pyqtSignal(str)

    def __init__(self, base_dir, settings):
        super().__init__()
        self.base_dir = base_dir
        self.settings = settings

    def run(self):
        try:
            rows, status, scan_payload = self.analyze()
            self.finished_ok.emit(rows, status, scan_payload)
        except Exception as e:
            import traceback
            traceback.print_exc()
            self.failed.emit(str(e))

    def _db_paths(self):
        data_dir = os.path.join(self.base_dir, "data")
        out = []
        for name in ("danbooru2026_clean.parquet", "danbooru_api_clean.parquet"):
            p = os.path.join(data_dir, name)
            if os.path.exists(p):
                out.append(p)
        return out

    def _make_dataset(self, paths):
        return ds.dataset(paths, format="parquet")

    def _columns_for_dataset(self, dataset):
        names = set(dataset.schema.names)
        wanted = ["created_at", "tag_string"]

        selected_types = set(self.settings.get("selected_types") or [])
        if not selected_types:
            selected_types = {category for _, category, _ in TAG_COLUMNS}

        # Only read category columns that can be useful for the selected type filter.
        for col, category, _ in TAG_COLUMNS:
            if category in selected_types and col in names:
                wanted.append(col)

        # For tag_string mode with type filtering, still read category columns so the
        # extension can identify which full tag_string tags belong to selected types.
        # For seed filtering, tag_string is always needed.

        # Artist-dominance filter needs tag_string_artist regardless of selected types.
        if self.settings.get("artist_dominance_enabled") and "tag_string_artist" in names:
            wanted.append("tag_string_artist")

        # De-dup while preserving order.
        seen = set()
        out = []
        for c in wanted:
            if c in names and c not in seen:
                seen.add(c)
                out.append(c)
        return out

    def _date_filter_expr(self, dataset):
        field = dataset.schema.field("created_at")
        arrow_type = field.type

        # Scan only the union of the two windows: [baseline_from, recent_to].
        start_scalar = _date_scalar_for_arrow(self.settings["baseline_from"], arrow_type)
        end_scalar = _date_scalar_for_arrow(self.settings["recent_to"], arrow_type)

        return (ds.field("created_at") >= start_scalar) & (ds.field("created_at") <= end_scalar)

    def _selected_tag_columns(self):
        selected_types = set(self.settings.get("selected_types") or [])
        if not selected_types:
            return TAG_COLUMNS
        return [(col, cat, color) for col, cat, color in TAG_COLUMNS if cat in selected_types]

    def _count_in_windows(self, dataset, columns, batch_size):
        """Single pass over the union date range.

        For each row, decide which window it falls into using its raw YYYY-MM-DD
        date (compared to baseline_from/baseline_to/recent_from/recent_to).
        Accumulates per-tag counts AND total post counts for normalization.

        When artist_dominance_enabled, also accumulates per-recent-tag artist
        counts so the scorer can drop tags whose recent appearances are
        dominated by a single artist.

        When num_workers > 1, batches are processed in a ThreadPoolExecutor.
        Bounded in-flight queue keeps peak memory predictable.
        """
        settings = self.settings
        seed_tags = list(settings["seed_tags"])
        include_seed_in_results = settings["include_seed_in_results"]
        count_mode = settings["count_mode"]
        track_artists = bool(settings.get("artist_dominance_enabled"))
        num_workers = max(1, int(settings.get("num_workers", 1)))

        # Note: excluded_tags is NOT applied here — it's applied at scoring time
        # so we can reuse cached counts when only the exclude list changes.
        skip_tags = set()
        if not include_seed_in_results:
            skip_tags.update(seed_tags)

        params = {
            "seed_tags": seed_tags,
            "seed_tags_set": set(seed_tags),
            "skip_tags": skip_tags,
            "count_mode": count_mode,
            "selected_cols": list(self._selected_tag_columns()),
            "track_artists": track_artists,
            "baseline_from": settings["baseline_from"],
            "baseline_to": settings["baseline_to"],
            "recent_from": settings["recent_from"],
            "recent_to": settings["recent_to"],
        }

        acc = {
            "recent_counts": Counter(),
            "baseline_counts": Counter(),
            "category_vote": {},
            "color_vote": {},
            "artist_tag_set": set(),
            "recent_artist_counts": {} if track_artists else None,
            "total_recent": 0,
            "total_baseline": 0,
            "scanned": 0,
            "matched_seed": 0,
        }

        date_filter = self._date_filter_expr(dataset)
        scanner = dataset.scanner(
            columns=columns,
            filter=date_filter,
            batch_size=batch_size,
            use_threads=True,
        )

        progress_every = 250000
        last_progress_at = 0

        def emit_progress():
            self.progress.emit(
                f"Scanned {acc['scanned']:,} rows in window, "
                f"seed-matched {acc['matched_seed']:,}, "
                f"unique recent tags {len(acc['recent_counts']):,}..."
            )

        if num_workers <= 1:
            # Single-threaded path — same memory profile as before.
            for batch in scanner.to_batches():
                pyd = batch.to_pydict()
                partial = _process_batch(pyd, params)
                _merge_partial(acc, partial)
                if acc["scanned"] - last_progress_at >= progress_every:
                    last_progress_at = acc["scanned"]
                    emit_progress()
        else:
            # Multi-threaded path. We keep at most `max_inflight` batches in
            # flight, where max_inflight = num_workers + a small buffer. This
            # bounds peak RAM: each in-flight batch carries its own pydict
            # plus the partial Counters it produces.
            max_inflight = num_workers + 2
            pending = deque()  # holds futures in submission order
            with ThreadPoolExecutor(max_workers=num_workers) as pool:
                for batch in scanner.to_batches():
                    pyd = batch.to_pydict()
                    fut = pool.submit(_process_batch, pyd, params)
                    pending.append(fut)
                    # Drain finished work, but also block when over the cap to
                    # avoid runaway memory.
                    while len(pending) >= max_inflight:
                        partial = pending.popleft().result()
                        _merge_partial(acc, partial)
                        if acc["scanned"] - last_progress_at >= progress_every:
                            last_progress_at = acc["scanned"]
                            emit_progress()
                # Drain remaining futures.
                while pending:
                    partial = pending.popleft().result()
                    _merge_partial(acc, partial)
                    if acc["scanned"] - last_progress_at >= progress_every:
                        last_progress_at = acc["scanned"]
                        emit_progress()

        return (
            acc["recent_counts"],
            acc["baseline_counts"],
            acc["category_vote"],
            acc["color_vote"],
            acc["total_recent"],
            acc["total_baseline"],
            acc["scanned"],
            acc["matched_seed"],
            acc["recent_artist_counts"],
            acc["artist_tag_set"],
        )

    def analyze(self):
        if pa is None or ds is None:
            return [], "Missing dependency: pyarrow. Install it with: pip install pyarrow", None

        paths = self._db_paths()
        if not paths:
            return [], "No parquet databases found in the data/ folder.", None

        selected_types = self.settings.get("selected_types") or []
        if not selected_types:
            return [], "Select at least one tag type.", None

        dataset = self._make_dataset(paths)
        columns = self._columns_for_dataset(dataset)

        if "created_at" not in columns or "tag_string" not in columns:
            return [], "Database must contain created_at and tag_string columns.", None

        missing_selected_cols = [
            col for col, category, _ in TAG_COLUMNS
            if category in selected_types and col not in columns
        ]
        if len(missing_selected_cols) == len(selected_types):
            return [], (
                "None of the selected tag-type columns exist in the database. "
                "Expected columns like tag_string_character, tag_string_artist, etc."
            ), None

        batch_size = self.settings["batch_size"]
        min_recent = self.settings["min_recent"]
        min_growth = self.settings["min_growth"]
        limit_tags = self.settings["limit_tags"]
        only_new = self.settings["only_new"]
        exclude_new = self.settings.get("exclude_new", False)

        baseline_from = self.settings["baseline_from"]
        baseline_to = self.settings["baseline_to"]
        recent_from = self.settings["recent_from"]
        recent_to = self.settings["recent_to"]

        type_label = ", ".join(selected_types)
        self.progress.emit(
            f"Scanning [{baseline_from} → {recent_to}] for type(s): {type_label}..."
        )

        (
            recent_counts,
            baseline_counts,
            category_vote,
            color_vote,
            total_recent,
            total_baseline,
            scanned_date_rows,
            matched_seed_rows,
            recent_artist_counts,
            artist_tag_set,
        ) = self._count_in_windows(dataset, columns, batch_size)

        if total_recent <= 0:
            return [], (
                f"No posts found in the explosion window "
                f"{recent_from} → {recent_to} (after seed/type filters)."
            ), None
        if total_baseline <= 0:
            return [], (
                f"No posts found in the baseline window "
                f"{baseline_from} → {baseline_to} (after seed/type filters)."
            ), None

        self.progress.emit("Scoring normalized explosions...")

        scan_payload = {
            "recent_counts": recent_counts,
            "baseline_counts": baseline_counts,
            "category_vote": category_vote,
            "color_vote": color_vote,
            "total_recent": total_recent,
            "total_baseline": total_baseline,
            "scanned_rows": scanned_date_rows,
            "matched_seed": matched_seed_rows,
            "recent_artist_counts": recent_artist_counts,
            "artist_tag_set": artist_tag_set,
        }

        rows, status = score_explosions(
            recent_counts=recent_counts,
            baseline_counts=baseline_counts,
            category_vote=category_vote,
            color_vote=color_vote,
            total_recent=total_recent,
            total_baseline=total_baseline,
            settings=self.settings,
            scanned_rows=scanned_date_rows,
            matched_seed=matched_seed_rows,
            cached=False,
            recent_artist_counts=recent_artist_counts,
            artist_tag_set=artist_tag_set,
        )
        return rows, status, scan_payload


class LowRamExplosionDialog(QDialog):
    def __init__(self, app):
        super().__init__(app)
        self.app = app
        self.worker = None
        self.results = []
        self._cache = None  # (key, scan_payload) — populated after a successful scan

        self.setWindowTitle("Low-RAM Normalized Tag Explosion Finder")
        self.resize(1240, 780)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        title = QLabel(
            "<b>💥 Low-RAM Normalized Tag Explosion Finder</b><br>"
            "Pick a <b>Baseline</b> window (the 'normal' period) and an <b>Explosion</b> "
            "window (the 'recent' period to look for spikes). Windows stay contiguous: "
            "baseline ends the day before the explosion starts."
        )
        title.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(title)

        cfg = QGroupBox("Configuration")
        cfg_layout = QVBoxLayout(cfg)

        # Determine sensible default windows. The user's preferred default is
        # explosion = last 1 month, baseline = 6 months immediately before that,
        # anchored on the dataset's latest created_at (not today's date).
        default_baseline_from, default_baseline_to, default_recent_from, default_recent_to = (
            self._default_windows()
        )
        latest_qdate = self._dataset_latest_qdate()
        if latest_qdate is not None:
            anchor_note = f"  ·  Defaults anchored on dataset latest: {latest_qdate.toString('yyyy-MM-dd')}"
        else:
            anchor_note = "  ·  Defaults anchored on today's date (dataset latest not available)"

        # Both windows on a single line for compactness.
        windows_box = QGroupBox(
            f"Time windows  (Baseline = 'normal' period, Explosion = where we look for spikes){anchor_note}"
        )
        windows_layout = QHBoxLayout(windows_box)

        baseline_label = QLabel("Baseline")
        baseline_label.setStyleSheet("font-weight: bold; color: #89b4fa;")
        windows_layout.addWidget(baseline_label)
        windows_layout.addWidget(QLabel("From:"))
        self.date_baseline_from = QDateEdit(default_baseline_from)
        self.date_baseline_from.setCalendarPopup(True)
        self.date_baseline_from.setDisplayFormat("yyyy-MM-dd")
        windows_layout.addWidget(self.date_baseline_from)

        windows_layout.addWidget(QLabel("To:"))
        self.date_baseline_to = QDateEdit(default_baseline_to)
        self.date_baseline_to.setCalendarPopup(True)
        self.date_baseline_to.setDisplayFormat("yyyy-MM-dd")
        windows_layout.addWidget(self.date_baseline_to)

        windows_layout.addSpacing(16)

        explosion_label = QLabel("💥 Explosion")
        explosion_label.setStyleSheet("font-weight: bold; color: #f38ba8;")
        windows_layout.addWidget(explosion_label)
        windows_layout.addWidget(QLabel("From:"))
        self.date_recent_from = QDateEdit(default_recent_from)
        self.date_recent_from.setCalendarPopup(True)
        self.date_recent_from.setDisplayFormat("yyyy-MM-dd")
        windows_layout.addWidget(self.date_recent_from)

        windows_layout.addWidget(QLabel("To:"))
        self.date_recent_to = QDateEdit(default_recent_to)
        self.date_recent_to.setCalendarPopup(True)
        self.date_recent_to.setDisplayFormat("yyyy-MM-dd")
        windows_layout.addWidget(self.date_recent_to)

        windows_layout.addSpacing(12)
        self.btn_link_windows = QToolButton()
        self.btn_link_windows.setText("🔗 Link")
        self.btn_link_windows.setCheckable(True)
        self.btn_link_windows.setChecked(True)
        self.btn_link_windows.setToolTip(
            "When linked, baseline-end and explosion-start are kept one day apart automatically. "
            "Uncheck to set them independently (a gap will simply be ignored during scoring)."
        )
        windows_layout.addWidget(self.btn_link_windows)

        windows_layout.addStretch()
        cfg_layout.addWidget(windows_box)

        # Wire up auto-link
        self.date_baseline_to.dateChanged.connect(self._on_baseline_to_changed)
        self.date_recent_from.dateChanged.connect(self._on_recent_from_changed)

        # Per-tag thresholds row
        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Min recent posts:"))
        self.spin_min_recent = QSpinBox()
        self.spin_min_recent.setRange(1, 1_000_000)
        self.spin_min_recent.setValue(25)
        self.spin_min_recent.setToolTip(
            "A tag must appear in at least this many posts inside the explosion window to be considered."
        )
        row1.addWidget(self.spin_min_recent)

        row1.addWidget(QLabel("Min growth ×:"))
        self.spin_growth = QSpinBox()
        self.spin_growth.setRange(1, 1000)
        self.spin_growth.setValue(3)
        self.spin_growth.setToolTip(
            "Recent share / baseline share must be at least this many times bigger."
        )
        row1.addWidget(self.spin_growth)

        row1.addWidget(QLabel("Limit:"))
        self.spin_limit = QSpinBox()
        self.spin_limit.setRange(10, 5000)
        self.spin_limit.setValue(500)
        row1.addWidget(self.spin_limit)

        row1.addStretch()
        cfg_layout.addLayout(row1)

        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Seed tags:"))
        self.input_seed = QLineEdit()
        self.input_seed.setPlaceholderText("Optional: 1girl, solo, blue_archive. Leave blank for global.")
        row2.addWidget(self.input_seed)
        cfg_layout.addLayout(row2)

        type_group = QGroupBox("Tag types to include")
        type_layout = QHBoxLayout(type_group)

        self.chk_artist = QCheckBox("Artist")
        self.chk_artist.setChecked(True)
        self.chk_artist.setStyleSheet("color: #f38ba8;")
        type_layout.addWidget(self.chk_artist)

        self.chk_copyright = QCheckBox("Copyright")
        self.chk_copyright.setChecked(True)
        self.chk_copyright.setStyleSheet("color: #cba6f7;")
        type_layout.addWidget(self.chk_copyright)

        self.chk_character = QCheckBox("Character")
        self.chk_character.setChecked(True)
        self.chk_character.setStyleSheet("color: #a6e3a1;")
        type_layout.addWidget(self.chk_character)

        self.chk_general = QCheckBox("General")
        self.chk_general.setChecked(True)
        self.chk_general.setStyleSheet("color: #89b4fa;")
        type_layout.addWidget(self.chk_general)

        self.chk_meta = QCheckBox("Meta")
        self.chk_meta.setChecked(False)
        self.chk_meta.setStyleSheet("color: #fab387;")
        type_layout.addWidget(self.chk_meta)

        type_layout.addStretch()

        self.btn_all_types = QPushButton("All")
        self.btn_all_types.clicked.connect(self.select_all_types)
        type_layout.addWidget(self.btn_all_types)

        self.btn_no_types = QPushButton("None")
        self.btn_no_types.clicked.connect(self.clear_all_types)
        type_layout.addWidget(self.btn_no_types)

        cfg_layout.addWidget(type_group)

        row3 = QHBoxLayout()

        row3.addWidget(QLabel("Batch size:"))
        self.spin_batch = QSpinBox()
        self.spin_batch.setRange(1_000, 200_000)
        self.spin_batch.setSingleStep(5_000)
        self.spin_batch.setValue(25_000)
        row3.addWidget(self.spin_batch)

        row3.addWidget(QLabel("Workers:"))
        self.spin_workers = QSpinBox()
        cpu_count = max(1, (os.cpu_count() or 1))
        self.spin_workers.setRange(1, max(8, cpu_count))
        self.spin_workers.setValue(1)
        self.spin_workers.setToolTip(
            "Number of parallel threads that process scanned batches.\n"
            "1 = single-threaded (lowest RAM, baseline behavior).\n"
            f">1 = parallel (faster on multi-core; up to {cpu_count} cores detected).\n\n"
            "Memory cost: peak RAM grows roughly linearly with workers, since each "
            "in-flight batch and its partial counters are held simultaneously. "
            "If you hit memory pressure, lower workers or batch size."
        )
        row3.addWidget(self.spin_workers)

        row3.addWidget(QLabel("Count mode:"))
        self.combo_count_mode = QComboBox()
        self.combo_count_mode.addItems(["category columns", "tag_string"])
        self.combo_count_mode.setCurrentText("category columns")
        self.combo_count_mode.setToolTip(
            "category columns is recommended for tag-type filtering and lower work. "
            "tag_string mode still restricts results to selected type columns."
        )
        row3.addWidget(self.combo_count_mode)

        self.chk_use_current_include = QCheckBox("Use current Include tags as seed")
        self.chk_use_current_include.setChecked(True)
        row3.addWidget(self.chk_use_current_include)

        self.chk_hide_current = QCheckBox("Hide current Include/Exclude")
        self.chk_hide_current.setChecked(True)
        row3.addWidget(self.chk_hide_current)

        self.chk_only_new = QCheckBox("Only zero-baseline tags")
        self.chk_only_new.setChecked(False)
        self.chk_only_new.setToolTip("Show only tags that have zero baseline count.")
        self.chk_only_new.toggled.connect(self._sync_new_tag_options)
        row3.addWidget(self.chk_only_new)

        self.chk_exclude_new = QCheckBox("Exclude new tags")
        self.chk_exclude_new.setChecked(False)
        self.chk_exclude_new.setToolTip("Hide tags with zero baseline count, so results are existing tags that grew.")
        self.chk_exclude_new.toggled.connect(self._sync_new_tag_options)
        row3.addWidget(self.chk_exclude_new)

        cfg_layout.addLayout(row3)

        # Artist-dominance row
        row_dom = QHBoxLayout()
        self.chk_artist_dom = QCheckBox("Drop tags dominated by one artist")
        self.chk_artist_dom.setChecked(False)
        self.chk_artist_dom.setToolTip(
            "Hide a tag if a single artist accounts for ≥ threshold % of the tag's "
            "solo-artist posts in the explosion window. Doesn't apply to artist tags themselves."
        )
        row_dom.addWidget(self.chk_artist_dom)

        row_dom.addWidget(QLabel("Threshold %:"))
        self.spin_artist_dom_pct = QSpinBox()
        self.spin_artist_dom_pct.setRange(10, 100)
        self.spin_artist_dom_pct.setValue(70)
        self.spin_artist_dom_pct.setSuffix(" %")
        row_dom.addWidget(self.spin_artist_dom_pct)

        row_dom.addWidget(QLabel("Min solo posts:"))
        self.spin_artist_dom_min = QSpinBox()
        self.spin_artist_dom_min.setRange(1, 1000)
        self.spin_artist_dom_min.setValue(5)
        self.spin_artist_dom_min.setToolTip(
            "Only apply the filter to tags with at least this many single-artist posts in the explosion window."
        )
        row_dom.addWidget(self.spin_artist_dom_min)

        row_dom.addStretch()
        cfg_layout.addLayout(row_dom)

        row4 = QHBoxLayout()
        row4.addStretch()
        self.btn_clear_cache = QPushButton("Clear Cache")
        self.btn_clear_cache.setToolTip(
            "Drop cached counts so the next click does a fresh parquet scan. "
            "Useful after the underlying database changes."
        )
        self.btn_clear_cache.clicked.connect(self._on_clear_cache)
        row4.addWidget(self.btn_clear_cache)

        self.btn_analyze = QPushButton("Find Normalized Exploding Tags")
        self.btn_analyze.clicked.connect(self.start)
        row4.addWidget(self.btn_analyze)
        cfg_layout.addLayout(row4)

        layout.addWidget(cfg)

        self.status = QLabel("Ready. Select tag types, then analyze.")
        self.status.setStyleSheet("color: #f9e2af; font-weight: bold;")
        layout.addWidget(self.status)

        self.table = QTableWidget(0, 10)
        self.table.setHorizontalHeaderLabels([
            "Tag",
            "Category",
            "Recent Count",
            "Baseline Count",
            "Recent %",
            "Baseline %",
            "Growth ×",
            "Δ %",
            "Score",
            "Why",
        ])
        for i in range(9):
            self.table.horizontalHeader().setSectionResizeMode(i, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(9, QHeaderView.ResizeMode.Stretch)
        self.table.setSortingEnabled(True)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        layout.addWidget(self.table)

        buttons = QHBoxLayout()

        self.btn_include = QPushButton("Add Selected to Include")
        self.btn_include.clicked.connect(self.add_selected_include)
        buttons.addWidget(self.btn_include)

        self.btn_exclude = QPushButton("Add Selected to Exclude")
        self.btn_exclude.clicked.connect(self.add_selected_exclude)
        buttons.addWidget(self.btn_exclude)

        self.btn_search = QPushButton("Show in Main Window")
        self.btn_search.setToolTip("Replace the main window's search with this tag and run it.")
        self.btn_search.clicked.connect(self.search_selected_alone)
        buttons.addWidget(self.btn_search)

        self.btn_open_danbooru = QPushButton("Open on Danbooru")
        self.btn_open_danbooru.setToolTip("Open this tag on danbooru.donmai.us in your browser.")
        self.btn_open_danbooru.clicked.connect(self.open_selected_on_danbooru)
        buttons.addWidget(self.btn_open_danbooru)

        self.btn_copy = QPushButton("Copy Selected Tag")
        self.btn_copy.clicked.connect(self.copy_selected)
        buttons.addWidget(self.btn_copy)

        layout.addLayout(buttons)

    def select_all_types(self):
        for cb in [self.chk_artist, self.chk_copyright, self.chk_character, self.chk_general, self.chk_meta]:
            cb.setChecked(True)

    def clear_all_types(self):
        for cb in [self.chk_artist, self.chk_copyright, self.chk_character, self.chk_general, self.chk_meta]:
            cb.setChecked(False)

    def _sync_new_tag_options(self):
        sender = self.sender()

        # These two options conflict:
        # - Only zero-baseline tags means "show new tags only"
        # - Exclude new tags means "hide zero-baseline tags"
        if sender is self.chk_only_new and self.chk_only_new.isChecked():
            self.chk_exclude_new.blockSignals(True)
            self.chk_exclude_new.setChecked(False)
            self.chk_exclude_new.blockSignals(False)

        elif sender is self.chk_exclude_new and self.chk_exclude_new.isChecked():
            self.chk_only_new.blockSignals(True)
            self.chk_only_new.setChecked(False)
            self.chk_only_new.blockSignals(False)

    def selected_types(self):
        out = []
        if self.chk_artist.isChecked():
            out.append("artist")
        if self.chk_copyright.isChecked():
            out.append("copyright")
        if self.chk_character.isChecked():
            out.append("character")
        if self.chk_general.isChecked():
            out.append("general")
        if self.chk_meta.isChecked():
            out.append("meta")
        return out

    def _base_dir(self):
        return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def _dataset_latest_qdate(self):
        """Return the latest created_at in the dataset as a QDate, or None.

        Cached on the dialog so reopening is instant. Uses a single Arrow scan
        on just the created_at column with use_threads=True; this is fast even
        on large parquets because we only read one column.
        """
        if getattr(self, "_dataset_latest_cache", "missing") != "missing":
            return self._dataset_latest_cache

        result = None
        try:
            if pa is None or ds is None:
                self._dataset_latest_cache = None
                return None

            data_dir = os.path.join(self._base_dir(), "data")
            paths = []
            for name in ("danbooru2026_clean.parquet", "danbooru_api_clean.parquet"):
                p = os.path.join(data_dir, name)
                if os.path.exists(p):
                    paths.append(p)
            if not paths:
                self._dataset_latest_cache = None
                return None

            dataset = ds.dataset(paths, format="parquet")
            if "created_at" not in set(dataset.schema.names):
                self._dataset_latest_cache = None
                return None

            import pyarrow.compute as pc
            scanner = dataset.scanner(columns=["created_at"], use_threads=True)
            max_val = None
            for batch in scanner.to_batches():
                if batch.num_rows == 0:
                    continue
                batch_max = pc.max(batch.column("created_at")).as_py()
                if batch_max is None:
                    continue
                if max_val is None or batch_max > max_val:
                    max_val = batch_max
            if max_val is not None:
                iso = str(max_val)[:10]
                if len(iso) == 10:
                    y, m, d = (int(x) for x in iso.split("-"))
                    result = QDate(y, m, d)
        except Exception:
            result = None

        self._dataset_latest_cache = result
        return result

    def _default_windows(self):
        """Default = explosion is the last month, baseline is the 6 months
        before that. Anchor is the dataset's latest created_at when available;
        otherwise today's date. Windows stay contiguous.
        """
        anchor = self._dataset_latest_qdate() or QDate.currentDate()
        recent_to = anchor
        recent_from = anchor.addDays(-30)
        baseline_to = recent_from.addDays(-1)
        baseline_from = baseline_to.addMonths(-6).addDays(1)
        return baseline_from, baseline_to, recent_from, recent_to

    def _on_baseline_to_changed(self, new_date):
        if not self.btn_link_windows.isChecked():
            return
        target = new_date.addDays(1)
        if self.date_recent_from.date() != target:
            self.date_recent_from.blockSignals(True)
            self.date_recent_from.setDate(target)
            self.date_recent_from.blockSignals(False)
        # Don't let recent_to slip behind recent_from.
        if self.date_recent_to.date() < target:
            self.date_recent_to.setDate(target)

    def _on_recent_from_changed(self, new_date):
        if not self.btn_link_windows.isChecked():
            return
        target = new_date.addDays(-1)
        if self.date_baseline_to.date() != target:
            self.date_baseline_to.blockSignals(True)
            self.date_baseline_to.setDate(target)
            self.date_baseline_to.blockSignals(False)
        if self.date_baseline_from.date() > target:
            self.date_baseline_from.setDate(target)

    def _text_tags_from_widget(self, name):
        widget = getattr(self.app, name, None)
        if widget is None or not hasattr(widget, "toPlainText"):
            return []
        return _parse_tags(widget.toPlainText())

    def _on_clear_cache(self):
        self._cache = None
        self.status.setText("Cache cleared. The next analyze will do a fresh database scan.")

    def _validate_windows(self):
        """Return (ok, error_message). Checks that windows are non-empty and ordered."""
        b_from = self.date_baseline_from.date()
        b_to = self.date_baseline_to.date()
        r_from = self.date_recent_from.date()
        r_to = self.date_recent_to.date()

        if b_from > b_to:
            return False, "Baseline 'From' date must be on or before Baseline 'To' date."
        if r_from > r_to:
            return False, "Explosion 'From' date must be on or before Explosion 'To' date."
        if r_from <= b_to:
            return False, (
                "Explosion window must start AFTER the baseline window ends "
                f"(baseline ends {b_to.toString('yyyy-MM-dd')}, "
                f"explosion starts {r_from.toString('yyyy-MM-dd')})."
            )
        return True, ""

    def _cache_key_from_settings(self, settings):
        """Inputs that change raw counts (require a re-scan).
        Excluded NOT included here, so toggling exclusion stays cache-friendly.
        Same for min_recent/min_growth/limit/only_new/exclude_new which are scoring-only.
        Same for num_workers — it changes speed and memory, not the result.
        """
        return (
            settings["baseline_from"],
            settings["baseline_to"],
            settings["recent_from"],
            settings["recent_to"],
            tuple(settings["selected_types"]),
            tuple(settings["seed_tags"]),
            settings["count_mode"],
            settings["batch_size"],
            settings["include_seed_in_results"],
        )

    def start(self):
        if self.worker is not None and self.worker.isRunning():
            return

        ok, err = self._validate_windows()
        if not ok:
            QMessageBox.warning(self, "Invalid date windows", err)
            return

        selected_types = self.selected_types()
        if not selected_types:
            QMessageBox.information(self, "No tag type selected", "Select at least one tag type.")
            return

        seed_tags = _parse_tags(self.input_seed.text())
        if self.chk_use_current_include.isChecked():
            seed_tags.extend(self._text_tags_from_widget("search_input"))
        seed_tags = list(dict.fromkeys(seed_tags))

        excluded = []
        if self.chk_hide_current.isChecked():
            excluded.extend(self._text_tags_from_widget("search_input"))
            excluded.extend(self._text_tags_from_widget("blacklist_input"))
        excluded = list(dict.fromkeys(excluded))

        baseline_from = _qdate_to_iso(self.date_baseline_from.date())
        baseline_to = _qdate_to_iso(self.date_baseline_to.date())
        recent_from = _qdate_to_iso(self.date_recent_from.date())
        recent_to = _qdate_to_iso(self.date_recent_to.date())

        settings = {
            "baseline_from": baseline_from,
            "baseline_to": baseline_to,
            "recent_from": recent_from,
            "recent_to": recent_to,
            "min_recent": self.spin_min_recent.value(),
            "min_growth": self.spin_growth.value(),
            "limit_tags": self.spin_limit.value(),
            "seed_tags": seed_tags,
            "excluded_tags": excluded,
            "selected_types": selected_types,
            "only_new": self.chk_only_new.isChecked(),
            "exclude_new": self.chk_exclude_new.isChecked(),
            "include_seed_in_results": False,
            "batch_size": self.spin_batch.value(),
            "count_mode": self.combo_count_mode.currentText(),
            "num_workers": self.spin_workers.value(),
            "artist_dominance_enabled": self.chk_artist_dom.isChecked(),
            "artist_dominance_threshold": self.spin_artist_dom_pct.value(),
            "artist_dominance_min_solo": self.spin_artist_dom_min.value(),
        }

        # Cache hit? Re-score off-thread, no parquet scan — UNLESS the user just
        # turned on artist-dominance and the cached payload doesn't include
        # artist data. In that case we have to rescan.
        key = self._cache_key_from_settings(settings)
        if self._cache is not None and self._cache[0] == key:
            payload = self._cache[1]
            need_artist_data = settings["artist_dominance_enabled"] and not payload.get("recent_artist_counts")
            if not need_artist_data:
                self.table.setRowCount(0)
                self.status.setText("Cache hit — re-scoring without re-scanning the database...")
                self.btn_analyze.setEnabled(False)
                self.btn_analyze.setText("Re-scoring...")
                # No new payload to cache (we're using the existing one).
                self._pending_cache_key = None
                self.worker = RescoreWorker(payload, settings)
                self.worker.progress.connect(self.status.setText)
                self.worker.finished_ok.connect(self.on_success)
                self.worker.failed.connect(self.on_error)
                self.worker.start()
                return

        workers_n = settings["num_workers"]
        worker_label = "single-threaded" if workers_n <= 1 else f"{workers_n} workers"
        self.table.setRowCount(0)
        self.status.setText(
            f"Starting scan ({worker_label}): baseline {baseline_from}→{baseline_to}, "
            f"explosion {recent_from}→{recent_to}, type(s): {', '.join(selected_types)}..."
        )
        self.btn_analyze.setEnabled(False)
        self.btn_analyze.setText("Analyzing...")

        self._pending_cache_key = key
        self.worker = LowRamExplosionWorker(self._base_dir(), settings)
        self.worker.progress.connect(self.status.setText)
        self.worker.finished_ok.connect(self.on_success)
        self.worker.failed.connect(self.on_error)
        self.worker.start()

    def on_success(self, rows, status, scan_payload):
        self.results = rows
        if scan_payload is not None and getattr(self, "_pending_cache_key", None) is not None:
            self._cache = (self._pending_cache_key, scan_payload)
        self._pending_cache_key = None
        self.populate()
        self.status.setText(status)
        self.btn_analyze.setEnabled(True)
        self.btn_analyze.setText("Find Normalized Exploding Tags")
        self.worker = None

    def on_error(self, error):
        self.status.setText(f"Error: {error}")
        QMessageBox.critical(self, "Low-RAM Normalized Tag Explosion Finder", error)
        self.btn_analyze.setEnabled(True)
        self.btn_analyze.setText("Find Normalized Exploding Tags")
        self.worker = None

    def populate(self):
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(self.results))

        for i, r in enumerate(self.results):
            color = QColor(r.get("color", DEFAULT_COLOR))

            tag_item = QTableWidgetItem(r["tag"])
            tag_item.setForeground(color)
            tag_item.setData(Qt.ItemDataRole.UserRole, r["tag"])
            self.table.setItem(i, 0, tag_item)

            category_item = QTableWidgetItem(r.get("category", ""))
            category_item.setForeground(color)
            self.table.setItem(i, 1, category_item)

            self.table.setItem(i, 2, NumericTableItem(f"{r['recent_count']:,}", r["recent_count"]))
            self.table.setItem(i, 3, NumericTableItem(f"{r['baseline_count']:,}", r["baseline_count"]))
            self.table.setItem(i, 4, NumericTableItem(f"{r['recent_pct']:.5f}%", r["recent_pct"]))
            self.table.setItem(i, 5, NumericTableItem(f"{r['baseline_pct']:.5f}%", r["baseline_pct"]))
            self.table.setItem(i, 6, NumericTableItem(f"{r['growth_x']:.2f}×", r["growth_x"]))
            self.table.setItem(i, 7, NumericTableItem(f"{r['delta_pct']:.5f}%", r["delta_pct"]))
            self.table.setItem(i, 8, NumericTableItem(f"{r['score']:.2f}", r["score"]))
            self.table.setItem(i, 9, QTableWidgetItem(r["why"]))

        self.table.setSortingEnabled(True)
        self.table.sortItems(8, Qt.SortOrder.DescendingOrder)

    def selected_tag(self):
        selected = self.table.selectedItems()
        if not selected:
            return None
        row = selected[0].row()
        item = self.table.item(row, 0)
        if not item:
            return None
        return item.data(Qt.ItemDataRole.UserRole) or item.text()

    def add_selected_include(self):
        tag = self.selected_tag()
        if not tag:
            QMessageBox.information(self, "No tag selected", "Select a tag first.")
            return
        if hasattr(self.app, "add_tag_to_include"):
            self.app.add_tag_to_include(tag)
        else:
            QApplication.clipboard().setText(tag)

    def add_selected_exclude(self):
        tag = self.selected_tag()
        if not tag:
            QMessageBox.information(self, "No tag selected", "Select a tag first.")
            return
        if hasattr(self.app, "add_tag_to_exclude"):
            self.app.add_tag_to_exclude(tag)
        else:
            QApplication.clipboard().setText(tag)

    def search_selected_alone(self):
        tag = self.selected_tag()
        if not tag:
            QMessageBox.information(self, "No tag selected", "Select a tag first.")
            return

        search_input = getattr(self.app, "search_input", None)
        blacklist_input = getattr(self.app, "blacklist_input", None)

        if search_input is not None and hasattr(search_input, "setPlainText"):
            search_input.setPlainText(tag)
        if blacklist_input is not None and hasattr(blacklist_input, "clear"):
            blacklist_input.clear()

        process = getattr(self.app, "process_data", None)
        if callable(process):
            process()

        self.close()

    def copy_selected(self):
        tag = self.selected_tag()
        if not tag:
            QMessageBox.information(self, "No tag selected", "Select a tag first.")
            return
        QApplication.clipboard().setText(tag)

    def open_selected_on_danbooru(self):
        tag = self.selected_tag()
        if not tag:
            QMessageBox.information(self, "No tag selected", "Select a tag first.")
            return
        url = f"https://danbooru.donmai.us/posts?tags={quote(tag)}"
        try:
            webbrowser.open(url, new=2)
        except Exception as e:
            QMessageBox.warning(self, "Could not open browser", f"{e}\n\nURL: {url}")


class LowRamTagExplosionPlugin:
    def __init__(self, app):
        self.app = app
        self.dialog = None
        self.btn = QPushButton("💥 Low-RAM Tag Explosions")
        self.btn.setToolTip("Find normalized exploding tags using date-filtered streaming and tag-type selection.")
        self.btn.clicked.connect(self.show_dialog)
        app.add_extension_button(self.btn)

    def show_dialog(self):
        if self.dialog is None:
            self.dialog = LowRamExplosionDialog(self.app)
        self.dialog.show()
        self.dialog.raise_()
        self.dialog.activateWindow()


def setup(app):
    plugin = LowRamTagExplosionPlugin(app)
    if not hasattr(app, "loaded_plugins"):
        app.loaded_plugins = []
    app.loaded_plugins.append(plugin)
