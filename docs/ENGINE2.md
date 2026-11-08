# Topology Engine 2.0

This is an additive, opt-in network assurance upgrade. The dependency-free v1
analysis and its byte-level report contract are preserved. Requirement
`schema_version: 2` selects the new engine, report format and interactive HTML.
The existing `analyze`, `verify` and `compare` commands work with both versions.
Package version is 2.0.0; the preserved v1 report engine remains 0.1.0.

## Capability and installation map

| Capability | Implementation | Additional installation |
|---|---|---|
| Directed/undirected mixed multigraphs | Per-edge direction; weak and strong components | None |
| Weighted routing | Dijkstra; independent Bellman–Ford check | None |
| Simultaneous failures | Disabled node/edge sets and up to 32 named scenarios | None |
| Resilience/redundancy | Directional edge removal; scoped edge/node survival ratios | None |
| Polygon relationships | GEOS predicates, holes and MultiPolygon | `pip install '.[geometry]'` |
| PostGIS snapshot | Read-only SQL capture to offline GeoJSON | `pip install '.[postgis]'` and a database |
| GeoJSON/GeoPackage | Strict engine feature contract; EPSG:4326 2D WKB | None |
| Geographic review | Self-contained SVG; pan, zoom, direction arrows, polygons | Browser with JavaScript for interaction |
| Independent verification | Separate route, cost and edge-removal algorithms | None |
| Provenance/audit | Captured declarations, input hashes, deterministic replay | None |

No plugin, database, geometry library, tile server, API key or network connection is
needed for core network analysis, GeoPackage conversion or replay of graph-only
studies. Polygon bundle replay needs the same optional geometry environment used
at creation; retain dependency versions for long-term reproducibility.

## Quick start

```sh
python -m pip install .
python -m spatial_topology analyze examples/network-v2.geojson \
  --requirements examples/requirements-v2.json --output review-v2
python -m spatial_topology verify review-v2
```

The synthetic example baseline passes, but its two outage scenarios have gaps.
Therefore `analyze` returns **1** after creating a complete bundle. `verify` returns
**0** for a consistent bundle even when requirements fail. Malformed inputs return
**2**. The report's `status` and `summary` describe the baseline; `study_status`
includes all scenarios. Read each scenario's own gaps and path checks.

## v2 feature contract

The v1 FeatureCollection envelope, explicit node and edge IDs, exact endpoint
matching, regional coordinates and strict unknown-field rejection still apply.
LineString properties additionally accept:

```json
{"kind":"edge","source":"A","target":"B","directed":true,"cost":4.5}
```

`directed` defaults to false. True permits traversal only from source to target.
`cost` is a finite number in [0, 1e12], never a boolean. Zero costs and parallel
links are supported. Missing cost uses the edge's approximate spherical metres.
Explicit costs are caller-defined units; prepare a consistent cost scale across
**all** edges. Costs are not automatically inferred travel times or capacities.

Routing minimizes cost. Reports separately sum geometric `distance_m` along the
selected route. Equal-cost ties are deterministic; they do not minimize distance
as a secondary objective. `max_distance_m` and optional `max_cost` apply to that
selected route, using unrounded sums. This is not resource-constrained routing:
another costlier route might satisfy a distance constraint when the chosen one
fails. Output sums are rounded to six places.

A v2 requirement retains all v1 required keys and paths, changes the version to 2,
and optionally adds `scenarios` and `provenance`. Each scenario has exactly:

```json
{"id":"combined-outage","disabled_nodes":["B"],"disabled_edges":["AC"]}
```

Failure sets are **added to** baseline disabled sets. Unknown objects and duplicate
IDs are rejected. There is no automatic combinatorial enumeration or stochastic
failure model. A named scenario is reported separately and compared against the
baseline gap set. Missing required objects remain missing observations.

Bounds: 300 nodes, 1000 edges, 100 polygons, **20,000 combined positions**, 100
required paths, 32 scenarios, and 4 MiB per JSON/bundle file. Studies also require
`(1 + scenario_count) * max(1, required_path_count) * (node_count + edge_count)^2`
not to exceed 25 million. This conservative traversal budget prevents accepting
combinations of individually bounded inputs that require excessive repeated work.
The engine remains a bounded regional analyzer, not a continental routing service.

## Direction, redundancy and scores

`components`, `bridges` and `articulation_nodes` describe **weak**, direction-ignored
connectivity. `strong_components` requires reachability in both directions. An
isolated node has no incident active edges, not merely no outgoing edges.

A path's `separating_edges` are edges on its selected directed route whose individual
removal destroys source-to-target reachability. Testing selected path edges is
sufficient: removing an edge outside that path leaves the selected route available.
Thus weak bridges are not used to decide directional redundancy. Failure exposure
has the existing `SINGLE_EDGE_FAILURE_EXPOSURE` code. Redundancy does not guarantee
fallback cost, distance, vertex disjointness, capacity or correlated-failure survival.

Resilience scores have an explicit, restricted denominator:

| Field | Denominator and meaning |
|---|---|
| `reachability_ratio` | Reachable required paths / all declared required paths |
| `single_edge_survival_ratio` | Surviving baseline-reachable path/active-edge-removal pairs / all such pairs |
| `single_node_survival_ratio` | Surviving baseline-reachable path/active-node-removal pairs / all such pairs |

Each declared path contributes once, including duplicate endpoint pairs with
different requirement IDs. Endpoint failure counts as path loss. An empty
denominator yields null, never a vacuous perfect score. Scores measure reachability;
they do not include distance/cost compliance and are not reliability probabilities.
Each scenario recomputes its scores relative to its own remaining active graph.

## Polygon topology

Add Polygon/MultiPolygon features with `kind: polygon` and optional `label`.
At least one explicit network node is still required. Rings must be closed and
bounded; self intersections, invalid holes and invalid multipolygons fail closed.
No automatic repair, snapping, junction inference or coordinate transformation occurs.

The optional geometry module reports polygon-pair `equals`, `touches`, `overlaps`,
`disjoint`, `contains`, `within` and positive-length `shared_boundary` predicates.
Pairs are sorted by ID: `contains` means source contains target and `within` means
source is within target. Node relations distinguish interior from boundary;
edge relations distinguish complete coverage from intersection. All features are
considered, including features disabled in the network scenario: these are static
geometry relationships, not scenario-specific geographic exposure estimates.

Predicates use planar longitude/latitude coordinates, without geodesic boundaries.
Antimeridian crossings and a combined longitude extent over 180 degrees are
rejected. This is an OGC-style predicate subset, not complete GIS topology rules,
standards certification, road noding or support for every GeoJSON feature type.

## Interoperability

```sh
python -m spatial_topology export-gpkg examples/network-v2.geojson --output network.gpkg
python -m spatial_topology import-gpkg network.gpkg --output captured.geojson
```

GeoPackage conversion uses standard SQLite metadata and GeoPackage binary geometry,
without GDAL. The engine-specific `topology_features` layer contains `fid`,
`feature_id`, JSON `properties`, and 2D EPSG:4326 `geom`. Point, LineString, Polygon
and MultiPolygon are supported. Other layers, CRS, dimensions, extended geometries
and arbitrary GIS attribute schemas need explicit preprocessing. The reader is
bounded to 16 MiB and 1400 rows. Destinations are created exclusively.

A GeoPackage timestamp records export time; **GeoPackage bytes are not reproducible
audit outputs**. Capture back to GeoJSON before analysis. WKB round trips preserve
numeric coordinates but can change integer/float representation and hence input
fingerprints. Geometry validation during conversion checks the bounded coordinate
contract; GEOS polygon validity is enforced when analyzing polygon studies.

For PostGIS, prepare a table/view with `feature_id` (globally unique text),
`properties` (JSON object following the feature contract), and `geom` (2D SRID 4326).
The adapter retrieves the captured geometry with `ST_AsGeoJSON`, without rewriting
the source or embedding credentials in provenance.

```sh
# Set SPATIAL_TOPOLOGY_DSN privately in your environment.
python -m spatial_topology import-postgis --schema public --table topology_source \
  --output captured.geojson
```

The CLI opens a read-only connection with connection and statement timeouts.
`--dsn-env` changes the environment variable name. SQL identifiers are quoted,
not interpolated. The Python API `read_postgis(connection, schema, table)` also
accepts a caller-owned psycopg connection; that caller owns transaction isolation,
timeouts and connection lifecycle. It issues one SELECT and never commits.
Offline audit bundles capture the snapshot, not a live connection. This adapter
does not provision PostGIS, edit datasets, transform CRS or establish source trust.

## Audit and independent verification

All five v1 bundle filenames and exclusive creation/replay rules remain in place.
V2 reports include `independent_verification`: separately constructed arcs,
Bellman–Ford minimum costs, selected-route validity and sums, and fixed-point
reachability after individual selected-edge removals. These checks run for the
baseline **and every scenario**. A disagreement stops bundle creation.

This is algorithm diversity within the same package. It is not an external audit:
geometry ingestion, distance calculations, requirements classification, components,
polygon predicates and resilience aggregates are not independently reimplemented.
`verify` also regenerates all report/HTML bytes, including the script CSP hash.

Optional provenance fields are `source`, `dataset_version`, timezone-bearing
ISO8601 `captured_at`, and lowercase 64-character `source_sha256`. These are
**unverified declarations** and are explicitly marked `authenticated: false`.
The declared external hash is not automatically checked against an unavailable
source. No timestamps are injected into deterministic analysis. Signatures,
trusted external receipts and source authenticity remain future work.

## Validation and benchmarks

```sh
python -m unittest discover -s tests -v
python tests/check_installed.py
python tests/check_v2_installed.py
python tests/check_researchos_installed.py
python benchmarks/network.py
```

Core tests run with no extras. The extra CI job installs geometry/PostGIS support
and runs a real PostGIS service using synthetic, transaction-local data. A local
live adapter test requires `SPATIAL_TOPOLOGY_TEST_DSN`; its absence is an explicit
skip. CI never uploads real network data or database credentials.

The benchmark exercises full v2 reports, including independent checks, for directed
synthetic graphs. Example local Python 3.12 measurements with tracemalloc enabled:

| Nodes | Edges | Wall seconds | Traced Python peak bytes |
|---:|---:|---:|---:|
| 16 | 32 | 0.0157 | 120382 |
| 40 | 80 | 0.0381 | 164728 |
| 80 | 160 | 0.1411 | 794256 |

These are observations from one environment, not guarantees or competitor
comparisons. Re-run the script on your target environment. Timings are not brittle
CI pass/fail thresholds. The benchmark does not measure GEOS, database I/O,
worst-case dense networks or production-scale throughput.
