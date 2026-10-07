# Project history and design notes

This project started as a one-person pipeline turning ~7 years of disconnected
TripWizard trip-plan exports into one continuous travel history (a gap
analysis, an itemized itinerary, and an interactive map), then got
generalized into the current tool: a header-based parser that works with any
export carrying TripWizard's column names, strict data-integrity checking
with no silent fixes, a tkinter UI, and installers for Windows and Linux.
This doc keeps the non-obvious reasoning behind several design choices that
aren't visible just from reading the code.

## Parsing subtleties

A few things about TripWizard's own export format aren't obvious from the
column schema alone (see [`src/rv_trip_visualizer/schema.py`](../src/rv_trip_visualizer/schema.py)
for the exact required headers):

- **Some exports have blank per-stop Arrival/Departure dates** - only the
  file's own "Start Date:" label and each row's Nights count are present.
  `parser.py` reconstructs dates by walking forward from Start Date,
  accumulating Nights. This is inference from the file's own internal
  consistency (a documented TripWizard export convention), not a guess about
  bad data - it's kept as general, intentional behavior.
- **Row order is not guaranteed to be chronological.** A real-world export
  was once found with rows in scrambled order (correct dates, wrong order)
  plus a duplicated opening row. `parser.py` sorts every file's stops by
  Arrival Date rather than trusting row order specifically because of this -
  treat that as a standing defensive measure, not dead code to remove.
- **TripWizard's own "Total" column has small rounding drift** against the
  sum of the "Miles" column - off by 1-2 miles in a handful of files.
  TripWizard rounds each leg's displayed Miles while keeping an unrounded
  running Total internally. `integrity.py` flags this when it exceeds a
  1-mile tolerance; below that, it's known, harmless TripWizard-side noise.

## Overlap resolution and mileage rescue

**Overlap resolution** (`merge.resolve_overlaps`): when a later export's
date range overlaps an earlier one (the trip was re-planned mid-trip and
re-exported), the later export wins for the overlapping dates - the earlier
file's covered stops are either dropped (fully superseded) or trimmed
(partially superseded). This is normal and expected for anyone who re-plans
and re-exports mid-trip.

**Mileage folding and rescue** - the one genuinely general algorithmic fix,
worth understanding before touching `merge.py` again:
- 0-night stops (gas, lunch, quick errands) aren't shown in the itinerary,
  but the distance TripWizard recorded to reach them is real, so it's
  folded forward onto the next real (>=1 night) stay.
- TripWizard always records a *new export's first stop* as "current
  location," Miles=0 - no travel logged yet in *that file*. Combined with
  overlap resolution dropping a previous file's stop at that same physical
  location, this can silently discard real mileage (first found via a case
  where a stop showed 0 mi when the source file clearly showed 35). Fixed
  generally: when overlap resolution is about to fully drop a stop, if its
  Location text exactly matches the new file's first stop AND that first
  stop's own miles is 0, the real mileage is rescued onto the survivor
  before the drop. This is keyed off TripWizard's own universal export
  convention (see `test_resolve_overlaps_rescues_mileage_on_the_gordonville_pattern`
  in `tests/test_merge.py`), not a one-off patch.

## Why there's no mechanism for correcting data in-tool

An earlier version of this project had a hand-maintained JSON file encoding
one person's personal memory of gaps TripWizard never recorded at all (a
multi-month stay with no export, a COVID-era stretch, a few "we just stayed
longer, never re-exported" cases), plus hardcoded city/state overrides for
venues whose Location text didn't parse. Both were removed deliberately:
`integrity.py` only ever reports problems - missing columns, unresolvable
state, missing coordinates, cross-file date gaps - it never patches them.
The fix for every finding is the same: go correct it in the source planning
tool and re-export, then re-run the check. This keeps the tool honest about
what's actually in the record versus what's been guessed, and makes the
"required headers" contract (schema.py) the same for every user instead of
accumulating one person's special cases.

**The one deliberate exception - and why it isn't actually an exception:**
TripWizard has no dedicated City/State field; `Location`/`Stop Name` are free
text, and plenty of real entries (a bare street address, an RV park name
with no city in it) will never parse into "City, ST" no matter what the user
does in TripWizard - there's nothing to fix. Blocking on that would be the
exact mistake the Miles/Total tolerance check made at first (see below):
treating an inherent limitation of the source format as if it were a
user-fixable error. `merge.resolve_city_state()` instead falls back to an
offline point-in-polygon lookup (`geocode.py`) against the same US state
boundary data `map_page.py` already bundles - a lat/lon sits inside exactly
one state, which is a derived geometric fact, not a guess, the same
category as the date-inference and mileage-rescue logic above. City has no
equivalent fallback (the nearest named place to a rural RV park often isn't
what anyone would call that stop), so it falls back to the stop's own raw
Location/Stop Name text instead of being invented.

`merge.STATES` also covers Canadian provinces (two-letter, no collision
with US codes) and Mexican states (three-letter postal/INEGI codes - e.g.
`SON` for Sonora) for the same reason: this is a standard, public code list,
not a fix aimed at any one venue. It's text-matching only - `geocode.py`'s
coordinate fallback stays US-only, since no MX/CA boundary polygons are
bundled - but that was enough to resolve the project's own real Sonora,
Mexico stop (`'...Puerto Peñasco (Rocky Point), SON, 83552'`) without
editing a single character of the source data: the state code was already
sitting right there in the Location text once the matcher recognized it.
"States / regions" stats (`itinerary_page.py`, `map_shell.html`) count
whatever's in each stay's `state` field, so Canadian/Mexican region codes
count toward those totals the same as US states do - no separate logic
needed there. The integrity check still blocks when coordinates are missing
entirely, or a stop is genuinely outside every region this tool knows about
(e.g. overseas travel).

**The same correction applies generally**: a check should only ever block
when there's something the user can actually go fix. The Miles-vs-Total
mismatch check was initially built as a blocking finding, then downgraded to
a non-blocking `report.log` note after running it against real data showed
it blocking on TripWizard's own ~2-mile internal rounding drift - a known,
harmless quirk of the export format itself (see "Parsing subtleties" above),
not a user error. If a future check idea can't be satisfied by editing the
source data, it shouldn't be a blocking finding.

## The map's architecture

`assets/map_shell.html` is a single self-contained file (SVG + vanilla JS,
no build-time framework) with a **dual-mode basemap**:

1. **SVG fallback** (always built first, zero dependencies): a hand-drawn
   US map using a real Albers projection (same formula/parameters D3 uses)
   over cached US Census TIGER-derived state boundaries (`assets/us-states.json`).
2. **Leaflet-enhanced mode**: loads Leaflet from a CDN, then USGS The
   National Map's topo tiles (`basemap.nationalmap.gov`) - shows roads,
   state boundaries, and city labels prominently, with no Referer/Origin
   policy to run into. Confirmed against this project's own basemap
   approach in a sibling project (Poudre-Map) before picking this URL.

Both modes share one `render()` function (branches on a `mapMode` variable)
and one set of interaction handlers: a timeline slider with real calendar-day
pacing (not stop-count pacing, so a 1-night stop flashes by and a 130-night
stay lingers), play/speed controls, hover tooltips, click-a-dot-to-jump-the-
timeline, per-year legend toggle + Select All/Clear All, and an "Itinerary"
popup showing the same year-grouped table as the standalone itinerary page.

**Why this isn't still pointed at `tile.openstreetmap.org`, and why the
fallback logic looks the way it does**: the first attempt (switch the tile
URL to OSM, rely on counting `tileerror` events to detect a blocked
provider) looked right and even demoed fine when served over http, but
still failed silently for `file://`. The actual mechanism turned out to be
more specific than "OSM rejects third-party embedding" or even "OSM 403s
`file://` pages" - inspecting the real response (`curl` with no Referer
header, which is exactly what a `file://` page sends - browsers omit
Referer entirely for local-scheme navigations, by spec) shows OSM's tile
server returns **HTTP 200** with a genuine, correctly-sized 256x256 PNG
reading "Access blocked" and an `x-blocked` response header. From Leaflet's
point of view (and `<img>`'s onerror in general), that's a *successful* tile
load - there's no error to count. The multi-second tileerror-counting
safety net never had a chance to fire, because nothing ever errored.

Two fixes followed from actually finding this: switching to USGS Topo
(confirmed via the same no-Referer `curl` test to serve real tiles, not a
block page), and adding `tileLooksBlocked()` - a one-tile `fetch()`
pre-flight, run *before* the UI ever switches into Leaflet mode, that
inspects the actual response status and headers rather than trusting an
`<img>` tag's load event. This is kept general (any `x-blocked`-style
header, not an OSM-specific check) since the failure mode - a tile host
serving a "successful", correctly-shaped placeholder instead of a real
error - isn't unique to OSM and could recur with a future provider. The
original tileload/tileerror safety net stays in place too, as a second line
of defense for a genuine runtime failure (real network error, timeout) after
the pre-flight has already passed.
Keep this pattern if the tile source ever changes again.

**Two CSS gotchas hit and fixed while building the map, worth knowing if
it's touched again:**
- *Flexbox + overflow*: a flex child needs explicit `min-height:0` to
  respect an ancestor's `max-height`+`overflow:hidden` (the default
  `min-height:auto` silently overrides it) - hit this in the itinerary
  modal, where content was being force-squeezed instead of scrolling. Also:
  don't use `display:flex` on a container just to get `gap` spacing if its
  children might be taller than the viewport - flex-shrink will crush them
  to fit instead of letting the container scroll. Fixed with plain block
  flow + margin-bottom instead.
- *Stacking contexts*: Leaflet's internal panes use z-index values up to
  ~700 for its own layering. The div wrapping the map (`.stage`) had
  `position:relative` but no z-index, which does NOT create a new stacking
  context - so Leaflet's internal z-index values leaked out and beat the
  itinerary modal (then z-index:50), burying it under the map. Fixed with
  `isolation:isolate` on `.stage` plus bumping the modal to z-index:1000.
  Verified with `document.elementFromPoint()` (an actual hit-test), not
  just comparing z-index numbers - computed z-index on Leaflet's internals
  isn't a reliable signal on its own.

## A note on how UI/map changes were tested

Throughout this project, UI/interaction changes were verified by driving the
actual rendered page via browser automation and JavaScript execution (not
just reading the code and assuming it works) - checking computed styles,
dispatching real events, hit-testing with `elementFromPoint`, forcing
failure paths by pointing CDN URLs at non-resolving hosts to confirm
fallback behavior actually degrades gracefully rather than assuming a
`catch` block does what it looks like it does. Worth keeping that bar for
anything involving the dual-mode map rendering or the integrity-checking
logic, where a silent wrong answer is easy to produce and easy to miss.
