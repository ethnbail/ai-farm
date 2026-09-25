"""Create development credentials locally without overwriting existing configuration."""

import os
import secrets
from pathlib import Path

root = Path(__file__).resolve().parents[1]
destination = root / ".env"
template = (root / ".env.example").read_text()
content = template.replace("REPLACE_WITH_LOCAL_PASSWORD", secrets.token_hex(24))
content = content.replace("REPLACE_WITH_REDIS_PASSWORD", secrets.token_hex(24))
try:
    descriptor = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
except FileExistsError:
    print(".env already exists; left unchanged.")
else:
    with os.fdopen(descriptor, "w") as target:
        target.write(content)
    print(
        "Created private .env with generated local credentials. No future API keys are needed."
    )
