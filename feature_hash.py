#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""FXJEFE feature hashing — scalable featureset identity (UTF-8)."""
from __future__ import annotations
import hashlib, json
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

def normalize_features(names: Optional[Iterable[str]]) -> List[str]:
    if not names:
        return []
    return [str(x).strip() for x in names if str(x).strip()]

# Ordered 29-feature contract from ALIGNMENT_V2 / config.json. Do not filter names.
CONTRACT_FEATURES = (
    "price", "atr", "ema_diff", "rsi", "garch_vol", "macd_diff", "vwap",
    "price_vwap_diff", "bb_position", "roc", "stochastic", "cci", "williams",
    "momentum", "realized_vol", "chaikin_vol", "adx", "rvi", "obv",
    "volume_delta", "ad_line", "vol_osc", "supertrend", "hma", "ichimoku_tenkan",
    "sar", "dpo", "spread", "sentiment",
)


def canonical_bytes(names: Sequence[str], *, mode: str = "set") -> bytes:
    feats = normalize_features(names)
    if mode == "ordered":
        payload = "\n".join(feats)
    else:
        payload = "\n".join(sorted(set(feats)))
    return payload.encode("utf-8")

def feature_hash(names: Optional[Iterable[str]], *, mode: str = "set", length: Optional[int] = None) -> str:
    digest = hashlib.sha256(canonical_bytes(list(names or []), mode=mode)).hexdigest()
    return digest[:int(length)] if length else digest

def feature_hash_pair(names: Optional[Iterable[str]]) -> Dict[str, Any]:
    feats = normalize_features(names)
    return {
        "count": len(feats),
        "unique": len(set(feats)),
        "hash_set": feature_hash(feats, mode="set"),
        "hash_set_short": feature_hash(feats, mode="set", length=16),
        "hash_ordered": feature_hash(feats, mode="ordered"),
        "hash_ordered_short": feature_hash(feats, mode="ordered", length=16),
    }

def hashes_equal(a, b, *, mode: str = "set") -> bool:
    return feature_hash(a, mode=mode) == feature_hash(b, mode=mode)

def all_roles_match(sets: Dict[str, Sequence[str]], *, mode: str = "set") -> Tuple[bool, Dict[str, Any]]:
    """Compare non-empty roles. Empty sets are ignored. Preference: model > ea > server > predict_mq5 > generatefeatures_mq5."""
    order = ["model", "ea", "server", "predict_mq5", "generatefeatures_mq5"]
    empty = feature_hash([], mode=mode)
    hashes = {k: feature_hash(v, mode=mode) for k, v in sets.items()}
    non_empty = {k: h for k, h in hashes.items() if h != empty}
    if not non_empty:
        return False, {
            "ok": False,
            "hashes": hashes,
            "mismatches": [],
            "reference": None,
            "reason": "no non-empty feature sets",
        }
    ref_key = next((k for k in order if k in non_empty), next(iter(non_empty)))
    ref = non_empty[ref_key]
    mismatches = [k for k, h in non_empty.items() if h != ref]
    return len(mismatches) == 0, {
        "ok": not mismatches,
        "reference": ref_key,
        "reference_hash": ref,
        "hashes": hashes,
        "mismatches": mismatches,
    }


def align_contract_row(payload: Optional[Dict[str, Any]], names: Optional[Sequence[str]] = None) -> List[float]:
    """Ordered contract vector. Missing keys become 0.0. Names are not filtered out."""
    names = list(names or CONTRACT_FEATURES)
    source = payload or {}
    row = []
    for name in names:
        value = source.get(name, 0.0) if isinstance(source, dict) else 0.0
        try:
            if value is None or value == "":
                row.append(0.0)
            else:
                row.append(float(value))
        except (TypeError, ValueError):
            row.append(0.0)
    return row

def snapshot_dict(names: Sequence[str], *, kind: str = "features") -> Dict[str, Any]:
    feats = normalize_features(names)
    pair = feature_hash_pair(feats)
    return {"kind": kind, "features": feats, "count": len(feats), "unique": len(set(feats)), **{k: pair[k] for k in pair if k.startswith("hash")}}

def run(project_dir=None, dry_run=True):
    demo = ["price", "atr", "rsi", "macd_diff"]
    reversed_demo = list(reversed(demo))
    set_same = feature_hash(demo, mode="set") == feature_hash(reversed_demo, mode="set")
    ordered_differs = feature_hash(demo, mode="ordered") != feature_hash(reversed_demo, mode="ordered")
    print("set", feature_hash(demo, mode="set", length=16))
    print("ordered", feature_hash(demo, mode="ordered", length=16))
    print("reverse_changes_ordered_only", set_same and ordered_differs)
    print("contract", len(CONTRACT_FEATURES))
    if not (set_same and ordered_differs and len(CONTRACT_FEATURES) == 29):
        return 1
    return 0


def main(argv=None):
    return run()


if __name__ == "__main__":
    import sys
    sys.exit(main())
