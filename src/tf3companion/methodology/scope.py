"""Where one save's reports and metadata live (the `SaveScope` indirection, design D11).

Until the per-save layout of `cross-platform-and-saves` exists, the single companion store is one
implicit save: the scope points at the data directory itself and the binding lives in
`<data>/methodology.json`. That fallback is explicitly *not* save isolation.
"""

from __future__ import annotations

import json
import os
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

SAVES_FOLDER = "saves"
SAVE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
FALLBACK_NOTE = ("No per-save layout is available: the single companion store acts as one implicit save, "
                 "so this output is not isolated per save.")


@dataclass(frozen=True)
class SaveScope:
    root: Path            # holds `reports/` (and, in the per-save layout, the store)
    metadata: Path        # JSON file holding the binding
    save_id: str | None = None
    isolated: bool = False

    # ---- construction ---------------------------------------------------------------
    @classmethod
    def fallback(cls, data: Path) -> "SaveScope":
        return cls(Path(data), Path(data) / "methodology.json", None, False)

    @classmethod
    def for_save(cls, data: Path, save_id: str) -> "SaveScope":
        """The folder `<data>/saves/<id>/` with its `save.json`; the folder must already exist."""
        if not SAVE_ID_RE.match(save_id):
            raise ValueError(f"Invalid save id {save_id!r}: use letters, digits, dot, underscore or hyphen.")
        root = Path(data) / SAVES_FOLDER / save_id
        if not root.is_dir():
            raise LookupError(f"Save '{save_id}' not found: {root} does not exist. "
                              "The per-save layout is created by the companion; omit --save to use the implicit save.")
        return cls(root, root / "save.json", save_id, True)

    # ---- layout --------------------------------------------------------------------
    @property
    def reports(self) -> Path:
        return self.root / "reports"

    def describe(self) -> dict[str, Any]:
        return {"saveId": self.save_id, "isolated": self.isolated, "root": str(self.root),
                **({} if self.isolated else {"note": FALLBACK_NOTE})}

    # ---- binding --------------------------------------------------------------------
    def _read(self) -> dict[str, Any]:
        if not self.metadata.is_file():
            return {}
        try:
            data = json.loads(self.metadata.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise ValueError(f"Cannot read {self.metadata}: {exc}. Fix or remove the file.") from exc
        if not isinstance(data, dict):
            raise ValueError(f"{self.metadata} must contain a JSON object.")
        return data

    def binding(self) -> str | None:
        value = self._read().get("methodology")
        if value is not None and (not isinstance(value, str) or not value.strip()):
            raise ValueError(f"{self.metadata}: 'methodology' must be a nonempty library reference.")
        return value

    def set_binding(self, ref: str | None) -> None:
        """Bind (or clear, with None) the save's default methodology, keeping other metadata keys."""
        data = self._read()
        if ref is None:
            data.pop("methodology", None)
        else:
            data["methodology"] = ref
        self.metadata.parent.mkdir(parents=True, exist_ok=True)
        text = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
        fd, tmp = tempfile.mkstemp(prefix=".meta.", dir=self.metadata.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(text)
            os.replace(tmp, self.metadata)
        except BaseException:
            Path(tmp).unlink(missing_ok=True)
            raise


@dataclass(frozen=True)
class UserPreference:
    """Dedicated preference owned by the library root, never a save scope."""

    root: Path

    @property
    def metadata(self) -> Path:
        return self.root / "user-methodology.json"

    def reference(self) -> str | None:
        if not self.metadata.exists():
            return None
        try:
            data = json.loads(self.metadata.read_text(encoding="utf-8"))
            if not isinstance(data, dict) or set(data) - {"schema", "methodology"}:
                raise ValueError("expected a preference object with only schema and methodology")
            if data.get("schema") != "tf3c-user-methodology/1":
                raise ValueError("unsupported preference schema")
            if "methodology" not in data:
                return None
            from .library import parse_ref
            value = data["methodology"]
            parse_ref(value)
            return value
        except (OSError, ValueError, TypeError) as exc:
            raise ValueError(f"Cannot read user default {self.metadata}: {exc}. "
                             "Use `tf3c methodology set-default REF` or `tf3c methodology clear-default`.") from exc

    def set_reference(self, ref: str | None) -> dict[str, Any]:
        previous, error = None, None
        try:
            previous = self.reference()
        except ValueError as exc:
            error = str(exc)
        if ref is not None or self.metadata.exists():
            from .library import _atomic_bytes
            data = {"schema": "tf3c-user-methodology/1"}
            if ref is not None:
                data["methodology"] = ref
            _atomic_bytes(self.metadata, (json.dumps(data, indent=2) + "\n").encode())
        return {"previousReference": previous, "previousError": error}
