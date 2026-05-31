import os

_ENV_PATH = os.path.join(os.path.dirname(__file__), "..", "..", ".env")


def load_env():
    """Load key=value pairs from .env into os.environ (does not overwrite existing env vars)."""
    path = os.path.abspath(_ENV_PATH)
    if not os.path.exists(path):
        return
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip()
            if key and key not in os.environ:
                os.environ[key] = value


def save_env(keys: dict[str, str]):
    """
    Write/update key=value pairs in .env.
    Preserves comments and existing keys not in `keys`.
    """
    path = os.path.abspath(_ENV_PATH)
    existing_lines: list[str] = []
    if os.path.exists(path):
        with open(path) as f:
            existing_lines = f.readlines()

    # Build a map of which keys already exist on which line
    updated_keys = set()
    new_lines: list[str] = []
    for line in existing_lines:
        stripped = line.strip()
        if stripped.startswith("#") or "=" not in stripped:
            new_lines.append(line)
            continue
        key = stripped.partition("=")[0].strip()
        if key in keys:
            new_lines.append(f"{key}={keys[key]}\n")
            updated_keys.add(key)
            os.environ[key] = keys[key]
        else:
            new_lines.append(line)

    # Append any new keys not previously in the file
    for key, value in keys.items():
        if key not in updated_keys:
            new_lines.append(f"{key}={value}\n")
            os.environ[key] = value

    with open(path, "w") as f:
        f.writelines(new_lines)


def get_key(name: str) -> str:
    """Return the current value of an API key from os.environ."""
    return os.environ.get(name, "")
