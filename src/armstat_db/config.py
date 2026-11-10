"""Project paths and defaults.

Every path can be overridden on the command line; the defaults assume this layout::

    workspace/
    ├── statbank-parser/   # https://github.com/opendataam/statbank-parser (English exports)
    └── arm-statbank-db/   # this repository
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

STATBANK_BASE = "https://statbank.armstat.am"
API_BASE = f"{STATBANK_BASE}/api/v1"
DATABASE_ID = "ArmStatBank"


@dataclass(frozen=True)
class Paths:
    parser_dir: Path
    source_dir: Path
    translations_dir: Path
    build_dir: Path

    @property
    def indicators(self) -> Path:
        return self.parser_dir / "indicators.jsonl"

    @property
    def exports(self) -> Path:
        return self.parser_dir / "exports"

    @property
    def database(self) -> Path:
        return self.build_dir / "armstat.duckdb"

    def api_cache(self, lang: str) -> Path:
        return self.source_dir / "api" / lang

    @property
    def overrides(self) -> Path:
        """English tables re-downloaded from the API because the parser export is faulty."""
        return self.source_dir / "api" / "en" / "overrides"


def default_paths(
    parser_dir: str | os.PathLike | None = None,
    source_dir: str | os.PathLike | None = None,
    translations_dir: str | os.PathLike | None = None,
    build_dir: str | os.PathLike | None = None,
) -> Paths:
    env_parser = os.environ.get("STATBANK_PARSER_DIR")
    return Paths(
        parser_dir=Path(parser_dir or env_parser or REPO_ROOT.parent / "statbank-parser"),
        source_dir=Path(source_dir or REPO_ROOT / "data" / "source"),
        translations_dir=Path(translations_dir or REPO_ROOT / "data" / "translations"),
        build_dir=Path(build_dir or REPO_ROOT / "build"),
    )
