"""Deterministic offline geographic SVG with keyboard and pointer pan/zoom."""
import base64
import hashlib
from html import escape
import json
import math
from .engine2 import parse_v2

SCRIPT = """const svg=document.querySelector('svg');const home=svg.getAttribute('viewBox').split(' ').map(Number);let box=home.slice(),drag=null;function draw(){svg.setAttribute('viewBox',box.join(' '))}function zoom(f){let w=box[2]*f,h=box[3]*f;if(w<1||w>100000)return;box=[box[0]+(box[2]-w)/2,box[1]+(box[3]-h)/2,w,h];draw()}document.querySelector('#in').onclick=()=>zoom(.8);document.querySelector('#out').onclick=()=>zoom(1.25);document.querySelector('#reset').onclick=()=>{box=home.slice();draw()};svg.onwheel=e=>{e.preventDefault();zoom(e.deltaY>0?1.1:.9)};svg.onpointerdown=e=>{drag=[e.clientX,e.clientY,box[0],box[1]];svg.setPointerCapture(e.pointerId)};svg.onpointermove=e=>{if(!drag)return;const r=svg.getBoundingClientRect();box[0]=drag[2]-(e.clientX-drag[0])*box[2]/r.width;box[1]=drag[3]-(e.clientY-drag[1])*box[3]/r.height;draw()};svg.onpointerup=svg.onpointercancel=()=>drag=null;svg.onkeydown=e=>{let step=box[2]/10;if(e.key==='ArrowLeft')box[0]-=step;else if(e.key==='ArrowRight')box[0]+=step;else if(e.key==='ArrowUp')box[1]-=step;else if(e.key==='ArrowDown')box[1]+=step;else if(e.key==='+')zoom(.8);else if(e.key==='-')zoom(1.25);else return;e.preventDefault();draw()};"""


def render_html_v2(data, report):
    network, options, polygons = parse_v2(data)
    coords = [n.coordinates for n in network.nodes.values()]
    coords += [p for e in network.edges.values() for p in e.coordinates]
    for feature in polygons:
        parts = feature['geometry']['coordinates']
        if feature['geometry']['type'] == 'Polygon':
            parts = [parts]
        coords += [p for part in parts for ring in part for p in ring]
    latitude = sum(p[1] for p in coords) / len(coords)
    factor = max(math.cos(math.radians(latitude)), .001)
    xs, ys = [p[0] * factor for p in coords], [p[1] for p in coords]
    xmin, xmax, ymin, ymax = min(xs), max(xs), min(ys), max(ys)
    scale = min(860 / max(xmax - xmin, .001), 400 / max(ymax - ymin, .001))
    def project(p):
        return 50 + (p[0] * factor - xmin) * scale, 450 - (p[1] - ymin) * scale
    shapes = []
    for feature in sorted(polygons, key=lambda f: f['id']):
        parts = feature['geometry']['coordinates']
        if feature['geometry']['type'] == 'Polygon':
            parts = [parts]
        commands = []
        for part in parts:
            for ring in part:
                points = [project(p) for p in ring]
                commands.append('M' + ' L'.join(f'{x:.4f},{y:.4f}' for x, y in points) + ' Z')
        shapes.append(f'<path d="{" ".join(commands)}" fill="#e0f2fe" stroke="#64748b" fill-rule="evenodd"><title>{escape(feature["id"])}</title></path>')
    for edge in sorted(network.edges.values(), key=lambda e: e.id):
        color = '#94a3b8' if edge.id in report['inactive_edges'] else '#b45309' if edge.id in report['bridges'] else '#2563eb'
        points = ' '.join(f'{x:.4f},{y:.4f}' for x, y in map(project, edge.coordinates))
        marker = ' marker-end="url(#arrow)"' if options[edge.id][0] else ''
        shapes.append(f'<polyline points="{points}" fill="none" stroke="{color}" stroke-width="2"{marker}><title>{escape(edge.id)}; cost {options[edge.id][1] if options[edge.id][1] is not None else "spherical metres"}</title></polyline>')
    for node in sorted(network.nodes.values(), key=lambda n: n.id):
        x, y = project(node.coordinates)
        color = '#94a3b8' if node.id in report['disabled_nodes'] else '#172033'
        shapes.append(f'<circle cx="{x:.4f}" cy="{y:.4f}" r="4" fill="{color}"><title>{escape(node.label)}</title></circle>')
        shapes.append(f'<text x="{x+6:.4f}" y="{y-6:.4f}" font-size="10">{escape(node.label)}</text>')
    digest = base64.b64encode(hashlib.sha256(SCRIPT.encode()).digest()).decode()
    payload = escape(json.dumps(report, sort_keys=True, indent=2))
    return ('<!doctype html><html lang="en"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; style-src \'unsafe-inline\'; script-src \'sha256-{digest}\'">'
            '<title>Topology Engine 2.0 audit</title><style>body{font:16px system-ui;max-width:1100px;margin:24px auto;padding:0 16px;color:#172033}'
            'svg{width:100%;background:#f1f5f9;touch-action:none}button{padding:10px;margin:4px}pre{white-space:pre-wrap;overflow-wrap:anywhere}</style></head><body>'
            '<h1>Topology Engine 2.0</h1>'
            f'<p>{report["status"]}: {report["summary"]["gap_count"]} baseline requirement gaps.</p>'
            '<button id="in" aria-label="Zoom in">+</button><button id="out" aria-label="Zoom out">−</button><button id="reset">Reset view</button>'
            '<svg tabindex="0" viewBox="0 0 960 500" role="img" aria-label="Interactive geographic topology; arrow keys pan, plus and minus zoom">'
            '<defs><marker id="arrow" viewBox="0 0 10 10" refX="10" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M0 0 L10 5 L0 10 Z" fill="#2563eb"/></marker></defs>'
            + ''.join(shapes) + '</svg><p>Drag to pan; scroll or use buttons to zoom. Arrowheads mark directed links. '
            'Blue: active; amber: weak bridges; gray: inactive. Regional equirectangular projection at mean feature latitude; '
            'no basemap, external resources, navigation or survey precision.</p>'
            '<h2>Audit, provenance and failure scenarios</h2><pre>' + payload + '</pre>'
            '<script>' + SCRIPT + '</script></body></html>\n')
