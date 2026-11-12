#!/usr/bin/env python3
"""Écarts relevés depuis hier 6 h (fichiers etat/ecarts-<date>.jsonl), regroupés : début, fin, nombre de relevés."""
import json, sys
from datetime import date, timedelta
from pathlib import Path
R = Path(__file__).resolve().parent; J = date.fromisoformat(sys.argv[1])
G = {}
for d in (J - timedelta(days=1), J):
    f = R / "etat" / f"ecarts-{d.isoformat()}.jsonl"
    if not f.exists(): continue
    for l in f.read_text().splitlines():
        try: x = json.loads(l)
        except ValueError: continue
        if x["quand"] < f"{(J - timedelta(days=1)).isoformat()}T06:00": continue
        k = (x["machine"], x["regle"], x["quoi"])
        g = G.setdefault(k, {"machine": x["machine"], "regle": x["regle"], "quoi": x["quoi"], "debut": x["quand"], "fin": x["quand"], "releves": 0})
        g["fin"] = max(g["fin"], x["quand"]); g["releves"] += 1
print(json.dumps(list(G.values()), ensure_ascii=False, indent=1))
