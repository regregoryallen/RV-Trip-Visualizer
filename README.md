# RV Trip Visualizer

Turns a set of RV-trip-planner export files into:

1. A data-integrity report - missing columns, unresolvable locations,
   mismatched mileage totals, and gaps in the record, each with a plain
   description of what to go fix and re-export.
2. An itemized itinerary - every overnight stay, with mileage - as a
   spreadsheet and a standalone web page.
3. An interactive map, color-coded by year, with a timeline scrubber and a
   real basemap showing roads, state boundaries, and city labels (with an
   offline hand-drawn fallback).

It was built around [TripWizard](https://tripwizard.rvlife.com/)'s `.xlsx`
export format, but works with any export that uses the same column headers
(see **Required columns** below) - extra columns, reordered columns, and
extra leading rows are all tolerated.

## Download

No GitHub account or command-line tools needed - these links always point
to the most recently built installer:

- **[Download for Windows](https://github.com/regregoryallen/RV-Trip-Visualizer/releases/latest/download/RVTripVisualizer-Setup.exe)**
- **[Download for Linux (AppImage)](https://github.com/regregoryallen/RV-Trip-Visualizer/releases/latest/download/RVTripVisualizer-x86_64.AppImage)**
  (`chmod +x` it, then run it directly - no installation step)

Rebuilt automatically on every push to `main`; see
[Releases](https://github.com/regregoryallen/RV-Trip-Visualizer/releases) for
the build history.

New to the app? See the **[User Guide](docs/USER_GUIDE.md)** - installing,
the Check Data / Build workflow, what each finding in the report means and
how to fix it, and what the output files are. The generated map and
itinerary pages also have their own **Help** link/section built in.

**There is no mechanism for correcting bad or incomplete source data from
inside this tool.** If the integrity check finds a problem, it stops there
and tells you what's wrong; the fix is always to correct it in the
originating planning tool and re-export. See
[`docs/HISTORY.md`](docs/HISTORY.md) for why.

## Required columns

A source file needs a sheet (any name - `Trip Summary` is checked first)
with a header row, somewhere in its first 20 rows, containing all of:

```
Stop Name, Miles, Total, Arrival Date, Nights, Departure Date,
Location, Latitude, Longitude
```

Any other columns may be present or absent and are ignored. Rows above the
header (a trip title, a "Start Date:" label, etc.) are fine.

## Running from source

```bash
python3 -m venv .venv
source .venv/bin/activate   # .venv\Scripts\activate on Windows
pip install -e .
python -m rv_trip_visualizer
```

This opens the desktop UI: select source files, click **Check Data**, fix
anything it flags, set your page titles and an output folder/filename, then
**Build**.

Run the test suite with `pip install -e ".[dev]"` then `pytest tests/`.

## Viewing the generated map with real tiles

The map checks the real tile host's response before switching away from the
offline hand-drawn SVG basemap (see `docs/HISTORY.md` for why that check
exists), so it degrades gracefully rather than showing broken tiles if a
tile host ever rejects it. If you want to guarantee real map tiles
regardless of how the file was opened, serve the output folder over plain
HTTP:

```bash
python3 -m http.server --directory /path/to/your/output 8000
```

then open `http://localhost:8000/<your-map-file>.html`.

## Building installers

Both installers wrap a [PyInstaller](https://pyinstaller.org/) one-dir build
(`packaging/pyinstaller.spec`) and are built per-OS by
[`.github/workflows/build-installers.yml`](.github/workflows/build-installers.yml)
on a tag push (`vX.Y.Z`) or manual workflow dispatch. To build locally:

**Windows** (requires [Inno Setup](https://jrsoftware.org/isinfo.php)):

```powershell
pip install -e ".[dev]"
pyinstaller packaging\pyinstaller.spec
iscc packaging\windows\setup.iss
```

**Linux** (requires `curl`; downloads `appimagetool` on first run):

```bash
pip install -e ".[dev]"
pyinstaller packaging/pyinstaller.spec
packaging/linux/build_appimage.sh
```

## Project layout

```
src/rv_trip_visualizer/
├── schema.py          required/optional column definitions + header lookup
├── parser.py           per-file row extraction
├── integrity.py         data-integrity checks (pure reporting, no fixes)
├── merge.py              overlap resolution + mileage folding/rescue
├── geocode.py             offline state-from-coordinates fallback
├── pipeline.py            orchestrates parse -> merge -> check -> write
├── itinerary_page.py       itinerary HTML renderer
├── map_page.py             map HTML renderer (Albers projection + Leaflet)
├── settings.py              persistent UI settings
├── ui.py                     tkinter desktop app
└── assets/                    HTML page shells + cached boundary GeoJSON
tests/            pytest suite - builds workbooks in-memory, no checked-in data
packaging/        PyInstaller spec, Inno Setup script, AppImage build script
docs/HISTORY.md   design rationale and non-obvious parsing/rendering notes
```
