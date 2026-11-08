# Contracts and analysis semantics

## Bounded ingestion

Inputs must be regular UTF8 JSON files; a UTF8 BOM is accepted. Each file is bounded
to 4 MiB. Duplicate keys, nonfinite values including overflowing floats, and nesting
over 64 levels are rejected. File metadata is compared before and after the bounded
read to detect changes during reading. These checks do not authenticate the source
or protect against a hostile administrator controlling the filesystem.

The GeoJSON object must have exactly `type` and `features`. Every feature must have
exactly `type`, `id`, `properties` and `geometry`; geometry must have exactly `type`
and `coordinates`. Point properties contain `kind: node` and optionally `label`.
LineString properties contain `kind: edge`, `source`, `target` only. Valid general
GeoJSON with other members requires preprocessing for this stricter application.

Limits are 300 nodes, 1000 edges, 20,000 total positions and 100 required paths.
IDs/labels contain 1–200 trimmed characters. IDs are case sensitive. Coordinates
contain exactly two finite numbers with longitude in [-180,180] and latitude in
[-90,90]. Booleans are not numeric coordinates. LineStrings contain at least two
positions. Self edges and dangling references are rejected. Multiple distinct edges
between the same endpoints are permitted.

The total network longitude extent, including line vertices, cannot exceed 180
degrees. A segment crossing more than 180 degrees in longitude is rejected. This
regional subset deliberately requires preprocessing antimeridian data. No tolerance
or snapping is applied to endpoint matching. A geometric crossing is not a graph
junction, and co-located nodes retain separate identities.

## Requirements

The exact v1 requirement keys are `schema_version`, `required_nodes`,
`required_paths`, `disabled_nodes`, `disabled_edges`. Identifier arrays are unique
and bounded. A required path has exactly `id`, `source`, `target`, `max_distance_m`,
`require_redundancy`. Endpoints must differ. Distance limits are finite numbers in
[0, 1e12]; redundancy is a JSON boolean. Requirement IDs must be unique. Empty
requirements are rejected to avoid a vacuous passing study.

Missing required nodes and route endpoints are assessed as missing observations,
not silently assigned zero or dropped. A known disabled node is unavailable rather
than missing. Coverage is active required nodes divided by all required nodes; it
is null when only paths are required. Disabling a node removes its incident edges
from the active graph. Disabling an unknown object is malformed configuration.

## Graph algorithms

All graph edges are undirected. Traversal order is deterministic by feature ID.
Connected components include isolated active nodes. A bridge is an individual active
edge whose removal increases component count. An articulation node is an active
node whose removal increases component count. Parallel edges are evaluated separately;
removing one of two parallel links does not disconnect its endpoints.

The implementation uses bounded removal-and-reachability tests for bridges and
articulation nodes. It prioritizes transparent behavior over large-scale performance.
With V vertices and E edges, this diagnostic portion costs approximately
O((V+E)*(V+E)); it is bounded by input limits, not suitable for continental networks.
Dijkstra routing uses nonnegative spherical segment sums. Equal-cost choices are
resolved deterministically by node and edge iteration order, not by an optimal
secondary objective. Zero-length links between distinct co-located nodes are valid.

Reported route distances are rounded to six decimal places, but threshold decisions
use unrounded values. A route can therefore display a value equal to a threshold
while narrowly failing it. Input floating-point precision and the approximate distance
model remain material limitations.

For a connected source and target, an active bridge on a selected path separates
those endpoints in every route. Thus absence of separating bridges means they remain
connected after any single active edge removal. This test does not claim vertex
disjointness or enforce distance limits on fallback routes. A threshold applies only
to the baseline shortest route.

## Gap codes and completion

| Code | Meaning |
|---|---|
| `MISSING_REQUIRED_NODE` | Required node absent from input |
| `UNAVAILABLE_REQUIRED_NODE` | Required node disabled in this scenario |
| `MISSING_ENDPOINT` | Required path endpoint absent |
| `UNAVAILABLE_ENDPOINT` | Required path endpoint disabled |
| `NO_PATH` | Both endpoints active but disconnected |
| `DISTANCE_LIMIT_EXCEEDED` | Shortest approximate route exceeds the declared limit |
| `SINGLE_EDGE_FAILURE_EXPOSURE` | Redundancy required but a bridge separates endpoints |

Topological findings and requirement gaps remain separate. An isolated extra node,
a bridge unrelated to a redundancy requirement, or multiple components can coexist
with `REQUIREMENTS_SATISFIED`. The status means only that the declared scoped
requirements pass in the supplied graph and scenario. It grants no approval.

## Determinism and replay

The engine uses no network, model calls, random generators or timestamps. Inputs
and requirements are canonicalized to sorted-key compact JSON with a final newline.
Fingerprints bind the JSON values, including array order and integer/float representation;
raw whitespace and object-key order are not preserved. A report records schema and
engine version plus input and requirement fingerprints.

A bundle stores canonical captured inputs, report, generated HTML, and a manifest.
Every output file is limited to 4 MiB. Verification requires the exact file set,
rejects bundle-directory and file symlinks, recomputes all outputs, and compares
bytes. Future engine versions that change output may reject older bundles. Keep
the original version available to reproduce its results; no cross-version migration
or compatibility promise is implemented.

Bundle verification establishes self-consistency against this implementation. It is
not an independent algorithm audit or a signature. An attacker able to replace all
inputs and regenerate everything can create another valid bundle. Use trusted
external fingerprints or signed provenance if source authenticity is required.

The destination directory is created exclusively; existing output is preserved.
Handled write failures remove the newly created partial directory. Abrupt process
termination may leave a partial directory, which verification rejects. Parent
directories must exist. Concurrent hostile modification is not a supported workflow.
The HTML embeds captured results and escaped labels, uses no scripts or external
resources, and includes an explicit schematic-map limitation.
