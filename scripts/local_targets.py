"""Read private, explicitly configured volume identities; never guess a target."""
import json,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def expected_volume(name):
    path=ROOT/'.local/targets.json'
    if not path.is_file():raise SystemExit('Configure .local/targets.json from config/targets.example.json before using device tools.')
    value=json.loads(path.read_text()).get(name)
    if not isinstance(value,str) or not re.fullmatch(r'[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}',value):
        raise SystemExit('Missing or invalid configured volume identity: '+name)
    return value.upper()
