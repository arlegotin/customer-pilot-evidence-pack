"""Small, inspectable packet builders; no product imports."""
import hashlib
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]


def write_json(path, value):
    path.write_text(json.dumps(value, sort_keys=True, allow_nan=False) + '\n')


def write_rows(path, rows):
    path.write_text(''.join(json.dumps(row, sort_keys=True, allow_nan=False) + '\n' for row in rows))


def make_packet(root, scenario='same-text-distinct-tasks'):
    target = Path(root) / 'packet'
    shutil.copytree(ROOT / 'fixtures/canonical/schema-small', target)
    return target


def rehash(root):
    manifest = json.loads((root / 'packet.json').read_text())
    manifest['hashes'] = {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
                          for p in sorted(root.rglob('*')) if p.is_file() and p.name != 'packet.json'}
    manifest['protocol_sha256'] = manifest['hashes']['protocol.json']
    write_json(root / 'packet.json', manifest)
