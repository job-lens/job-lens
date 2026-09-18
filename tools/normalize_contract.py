"""Normalize descriptions in the imported YAML contract before generating API types."""
import json
import re
from pathlib import Path

path = Path("contracts/openapi.yaml")
source = path.read_text(encoding="utf-8")
source = re.sub(
    r'description: ([^{}"\n][^{}\n]*?)(?=, [A-Za-z_$][A-Za-z0-9_$-]*:|})',
    lambda match: "description: " + json.dumps(match.group(1).strip(), ensure_ascii=False),
    source,
)
path.write_text(source, encoding="utf-8")
