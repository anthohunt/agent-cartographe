#!/usr/bin/env python3
"""Partie « Cartographe » du rapport du matin : relecture de Claude du jour (si elle a eu lieu) ou écarts du programme seul."""
import os, json, subprocess, sys
from pathlib import Path
R = Path(__file__).resolve().parent; J = sys.argv[1]
E = json.loads(subprocess.run(["python3", str(R / "ecarts-jour.py"), J], capture_output=True, text=True).stdout or "[]")
try: c = json.loads((R / "etat" / "claude.json").read_text())
except Exception: c = {}
if c.get("date") != J: c = {}
L = ["Carte : " + (os.environ.get("TABLEAU_URL") or open(os.path.expanduser("~/.config/agents/tableau-url")).read().strip()) + "/carte/", ""]
if c.get("resume"): L += [c["resume"], ""]
ec = c.get("ecarts") or []
if ec:
    L.append("Écarts aux règles (relus par Claude) :")
    for x in ec:
        L.append(f"• {x.get('machine')} — {x.get('regle')} : " + ("réel. " if x.get("reel") else "faux écart. ") + f"{x.get('explication', '')}"
                 + (f" Correction : {x['correction']} ({x.get('qui', '')})." if x.get("reel") and x.get("correction") else ""))
elif E:
    L.append("Écarts aux règles depuis hier 6 h (programme seul, la relecture de Claude n'a pas eu lieu) :")
    L += [f"• {x['machine']} — {x['regle']} : {x['quoi']} (de {x['debut'][11:16]} à {x['fin'][11:16]}, {x['releves']} relevé(s))" for x in E]
else:
    L.append("Aucun écart aux règles depuis hier 6 h.")
if c.get("vu_en_plus"): L += ["", "Vu en plus :"] + [f"• {x}" for x in c["vu_en_plus"]]
n = sum(1 for x in ec if x.get("reel")) if ec else len(E)
sujet = f"Cartographe : {n} écart(s) aux règles" if n else "Cartographe : aucun écart"
t = R / "logs" / f"{J}-depot.txt"; t.write_text("\n".join(L), encoding="utf-8")
if "--apercu" in sys.argv: print(sujet + "\n" + "\n".join(L)); sys.exit()
sys.exit(subprocess.run(["/home/claude/mail-du-matin/deposer.py", "cartographe", "--date", J, "--sujet", sujet, "--text-file", str(t)]).returncode)
