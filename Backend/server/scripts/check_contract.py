import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.main import app


def contract_endpoints(path: Path) -> set[tuple[str, str]]:
    text = path.read_text(encoding="utf-8")
    block = text.split("# Endpoints", 1)[1].split("\n#", 1)[0]
    return {
        (match.group(1).lower(), match.group(2))
        for line in block.splitlines()
        if (match := re.match(r"^(GET|POST|PUT|PATCH|DELETE)\s+(\S+)", line.strip()))
    }


def openapi_endpoints() -> set[tuple[str, str]]:
    schema = app.openapi()
    return {
        (method.lower(), path) for path, methods in schema["paths"].items() for method in methods
    }


def main() -> int:
    root = Path(__file__).resolve().parents[2]
    contract = contract_endpoints(root / "docs" / "CONTRACT.md")
    actual = openapi_endpoints()
    missing, extra = sorted(contract - actual), sorted(actual - contract)
    if missing or extra:
        print(f"Missing from OpenAPI: {missing}")
        print(f"Extra in OpenAPI: {extra}")
        return 1
    print(f"Contract matches OpenAPI ({len(contract)} endpoints).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
