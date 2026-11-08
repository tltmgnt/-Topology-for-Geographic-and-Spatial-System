"""Bounded offline scenario execution and exact replay bundles."""
import json
from pathlib import Path
import shutil
from .core import canonical, replay

FILES={'scenario.json','ledger.json','report.json'}


def load(path):
    path=Path(path)
    if path.is_symlink() or not path.is_file() or path.stat().st_size>8*1024*1024: raise ValueError('Expected a regular JSON file no larger than 8 MiB')
    raw=path.read_bytes()
    if len(raw)>8*1024*1024: raise ValueError('Input too large')
    def pairs(items):
        result={}
        for key,value in items:
            if key in result: raise ValueError('Duplicate JSON key')
            result[key]=value
        return result
    result=json.loads(raw.decode('utf-8-sig'),object_pairs_hook=pairs,parse_constant=lambda _:(_ for _ in ()).throw(ValueError('Nonfinite JSON number')))
    # Overflowing JSON floats are also rejected by canonical serialization.
    canonical(result)
    return result


def contents(scenario):
    controller=replay(scenario)
    return {'scenario.json':canonical(scenario),'ledger.json':canonical(controller.ledger),'report.json':canonical(controller.report())}


def write_bundle(scenario,destination):
    expected=contents(scenario); destination=Path(destination)
    if any(len(value.encode())>8*1024*1024 for value in expected.values()): raise ValueError('Output exceeds 8 MiB per file')
    destination.mkdir() # exclusive; parent must already exist
    try:
        for name,value in expected.items(): (destination/name).write_text(value,encoding='utf-8')
    except BaseException:
        shutil.rmtree(destination); raise
    return json.loads(expected['report.json'])


def verify_bundle(destination):
    destination=Path(destination)
    if destination.is_symlink() or not destination.is_dir() or {p.name for p in destination.iterdir()}!=FILES: raise ValueError('Invalid bundle file set')
    captured={name:load(destination/name) for name in FILES}
    expected=contents(captured['scenario.json'])
    for name,value in expected.items():
        if (destination/name).read_bytes()!=value.encode(): raise ValueError('Replay mismatch: '+name)
    return captured['report.json']
