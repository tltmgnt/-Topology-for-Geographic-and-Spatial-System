"""Self-contained script-free HTML and schematic SVG rendering."""
from html import escape
import json
from .model import parse_network


def render_html(geojson, report):
    if report['schema_version'] == 2:
        from .render2 import render_html_v2
        return render_html_v2(geojson, report)
    network = parse_network(geojson)
    coordinates = [p for node in network.nodes.values() for p in [node.coordinates]]
    coordinates += [p for edge in network.edges.values() for p in edge.coordinates]
    xs, ys = [p[0] for p in coordinates], [p[1] for p in coordinates]
    xmin, xmax, ymin, ymax = min(xs), max(xs), min(ys), max(ys)
    dx, dy = max(xmax - xmin, 0.001), max(ymax - ymin, 0.001)

    def project(p):
        return (50 + 860 * (p[0] - xmin) / dx, 450 - 400 * (p[1] - ymin) / dy)

    shapes = []
    for edge in sorted(network.edges.values(), key=lambda e: e.id):
        color = '#94a3b8' if edge.id in report['inactive_edges'] else '#b45309' if edge.id in report['bridges'] else '#2563eb'
        points = ' '.join(f'{x:.3f},{y:.3f}' for x, y in map(project, edge.coordinates))
        shapes.append(f'<polyline points="{points}" stroke="{color}" stroke-width="3" fill="none"><title>{escape(edge.id)}</title></polyline>')
    for node in sorted(network.nodes.values(), key=lambda n: n.id):
        x, y = project(node.coordinates)
        color = '#94a3b8' if node.id in report['disabled_nodes'] else '#0f172a'
        shapes.append(f'<circle cx="{x:.3f}" cy="{y:.3f}" r="5" fill="{color}"><title>{escape(node.label)}</title></circle>')
        label = escape(node.label[:24] + ('…' if len(node.label) > 24 else ''))
        shapes.append(f'<text x="{x + 8:.3f}" y="{y - 8:.3f}" font-size="12">{label}</text>')
    rows = ''.join('<tr><td>' + escape(item['requirement']['id']) + '</td><td>' + item['status']
                   + '</td><td>' + escape(', '.join(item['reasons']) or 'Within declared limits') + '</td></tr>'
                   for item in report['path_checks'])
    payload = escape(json.dumps(report, sort_keys=True, indent=2))
    return ('<!doctype html><html lang="en"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width, initial-scale=1">'
            '<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; style-src \'unsafe-inline\'">'
            '<title>Spatial topology review</title><style>'
            'body{font:16px system-ui,sans-serif;max-width:1100px;margin:32px auto;padding:0 20px;color:#172033}'
            'h1{font-size:32px}.map{overflow:auto}svg{width:100%;min-width:640px;height:auto;background:#f1f5f9;border-radius:12px}'
            'table{border-collapse:collapse;width:100%;table-layout:fixed}td,th{overflow-wrap:anywhere}td,th{border:1px solid #cbd5e1;padding:10px;text-align:left}'
            'pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#f8fafc;padding:16px}'
            '</style></head><body><h1>Geographic and spatial topology</h1>'
            '<p>Offline regional network review. Synthetic examples demonstrate software behavior only.</p>'
            f'<h2>{report["status"]}</h2><p>{report["summary"]["gap_count"]} requirement gaps detected.</p>'
            '<div class="map"><svg viewBox="0 0 960 500" role="img" aria-label="Schematic geographic network">'
            + ''.join(shapes) + '</svg></div><p>Blue links are active; amber links are graph bridges; gray features are inactive. '
            'Longitude and latitude schematic, independently scaled axes. Not a navigation or survey map.</p>'
            '<h2>Required paths</h2><table><thead><tr><th>Requirement</th><th>Status</th><th>Finding</th></tr></thead><tbody>'
            + rows + '</tbody></table><h2>Complete analysis and provenance</h2><pre>' + payload
            + '</pre></body></html>\n')
