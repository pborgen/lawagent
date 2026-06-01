"""Token → dollar estimates from `config/pricing.yaml`.

Cost is computed once, at the moment a usage row is written, and stored
on the row. So the dashboard's totals stay stable even when list prices
change here later — editing this file only affects future calls.

Unknown models (anything without a YAML entry, e.g. fully local models)
return None, which the UI renders as "—" rather than a misleading $0.00.
"""
from __future__ import annotations

from decimal import Decimal
from functools import lru_cache
from pathlib import Path
from typing import Optional

import yaml

from settings import get_settings

_MTOK = Decimal(1_000_000)


def _pricing_path() -> Path:
    """Locate the pricing YAML.

    Honors `LAWAGENT_PRICING_FILE`; otherwise `config/pricing.yaml` at the
    repo root (two levels above this `packages/llm/` file), mirroring how
    `profiles.py` resolves `config/profiles.yaml`.
    """
    override = get_settings().pricing_file
    if override:
        return Path(override).expanduser()
    return Path(__file__).resolve().parents[2] / "config" / "pricing.yaml"


@lru_cache(maxsize=1)
def _price_table() -> dict[str, tuple[Decimal, Decimal]]:
    """Load `{model_lowercased: (input_per_mtok, output_per_mtok)}` (cached)."""
    path = _pricing_path()
    if not path.exists():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    table: dict[str, tuple[Decimal, Decimal]] = {}
    for name, rates in (data.get("models") or {}).items():
        table[str(name).lower()] = (
            Decimal(str(rates.get("input_per_mtok", 0))),
            Decimal(str(rates.get("output_per_mtok", 0))),
        )
    return table


def cost_usd(model: str, input_tokens: int, output_tokens: int) -> Optional[Decimal]:
    """Estimated USD cost for one call, or None if the model isn't priced.

    Quantized to 6 decimal places to match the DB column (Numeric(12, 6)).
    """
    rates = _price_table().get((model or "").lower())
    if rates is None:
        return None
    in_rate, out_rate = rates
    total = (Decimal(input_tokens) * in_rate + Decimal(output_tokens) * out_rate) / _MTOK
    return total.quantize(Decimal("0.000001"))
