#!/usr/bin/env python3
"""Page de la carte (choix A d'Anthony, 12/11) : schéma cliquable des machines + fiche de chaque machine (jobs, agents,
sessions, services) + écarts aux règles. Lit etat/carte.json (releve.py) et etat/claude.json (relecture de nuit, facultative).
Écrit /home/claude/agents-permanents-dash/carte/index.html (servi par le tableau des agents permanents, port 7910)."""
import html, json, re
from datetime import datetime
from pathlib import Path
ICI = Path(__file__).resolve().parent
OUT = Path("/home/claude/agents-permanents-dash/carte"); OUT.mkdir(parents=True, exist_ok=True)
e = lambda s: html.escape(str(s if s is not None else ""))
_ici = Path(__file__).resolve().parent; _cf = _ici / "etat" / "machines.local.json"
CONF_LEG = json.loads((_cf if _cf.exists() else _ici / "machines.exemple.json").read_text()).get("legende_postes", "Postes prêtés")
C = json.loads((ICI / "etat" / "carte.json").read_text())
CL = {}
try: CL = json.loads((ICI / "etat" / "claude.json").read_text())
except Exception: pass
M = C["machines"]
ORDRE = ["vps", "cloud", "vr-1", "vr-2", "vr-3", "vr-4", "vr-5", "vr-6", "postes", "tour", "laptop", "oracle"]
autres = [k for k in M if k not in ORDRE]
TITRES = {"postes": "Postes IOMEGA (poste non précisé)", "autre": "Sans machine (en pause ou en attente)"}
actif = lambda j: bool(re.search(r"en cours|tourne|actif|lanc|en place|programm", (j.get("etat") or "").lower()))

def etat_machine(m):
    if m.get("en_ligne") is False: return "ko", "éteinte ou injoignable"
    if m["cle"] == "vps" and (m.get("charge", 0) > 8 or m.get("echange_pct", 0) > 80): return "warn", "chargé"
    if m.get("parc"): return ("ok", "libre") if m["parc"].get("libre") else ("busy", "occupé : " + (m["parc"].get("occupe_par") or "?"))
    if m.get("en_ligne") is None: return "na", ""
    return "ok", "en ligne"

ecarts_par = {}
for x in C["ecarts"]: ecarts_par.setdefault(x["machine"], []).append(x)

# ---------------------------------------------------------------- schéma (SVG, connexions à angles droits)
noeuds = [("cloud", 30), ("vr-1", 190), ("vr-2", 290), ("vr-3", 390), ("vr-4", 490), ("vr-5", 590), ("vr-6", 690), ("tour", 820), ("laptop", 940), ("oracle", 1060)]
S = ['<svg viewBox="0 0 1160 300" role="img" aria-label="Schéma : le VPS relié par Tailscale aux postes IOMEGA, à la tour, au laptop, au serveur Oracle et aux sessions cloud">']
S.append('<line x1="580" y1="96" x2="580" y2="150" class="fil"/><line x1="100" y1="150" x2="1120" y2="150" class="fil"/>')
def boite(k, x, y, w, h, grand=False):
    m = M.get(k) or {"cle": k, "titre": k, "jobs": [], "agents": [], "en_ligne": None}
    st, _ = etat_machine(m); nj = len([j for j in m.get("jobs", []) if actif(j)]); na = len(m.get("agents", []))
    titre = {"vps": "VPS", "cloud": "Claude cloud", "oracle": "Oracle", "tour": "Tour", "laptop": "Laptop"}.get(k, k)
    alerte = '<circle cx="%d" cy="%d" r="7" class="alerte"/>' % (x + w - 8, y + 8) if ecarts_par.get(k) else ""
    sous = f"{nj} job{'s' if nj > 1 else ''} actif{'s' if nj > 1 else ''} · {na} agents" if grand else f"{nj} actif" + ("s" if nj > 1 else "")
    return (f'<a href="#m-{k}"><g class="noeud {st}"><rect x="{x}" y="{y}" width="{w}" height="{h}" rx="10"/>'
            f'<text x="{x + w/2}" y="{y + (30 if grand else 26)}" class="t">{e(titre)}</text>'
            f'<text x="{x + w/2}" y="{y + (52 if grand else 46)}" class="s">{e(sous)}</text>{alerte}</g></a>')
S.append(boite("vps", 470, 20, 220, 76, True))
for k, cx in noeuds:
    S.append(f'<line x1="{cx + 40}" y1="150" x2="{cx + 40}" y2="190" class="fil"/>')
    S.append(boite(k, cx, 190, 80 if k.startswith("vr-") else 100, 64))
S.append('<text x="120" y="282" class="leg">' + e(CONF_LEG) + '</text></svg>')

# ---------------------------------------------------------------- fiches des machines
def liste(titre, L, f):
    if not L: return ""
    return f'<details{" open" if titre.startswith("Jobs") else ""}><summary>{e(titre)} ({len(L)})</summary><ul>' + "".join(f"<li>{f(x)}</li>" for x in L) + "</ul></details>"
F = []
for k in ORDRE + autres:
    m = M.get(k)
    if not m or (k in ("postes", "autre") and not m["jobs"]): continue
    st, lib = etat_machine(m)
    info = []
    if k == "vps": info.append(f"charge {m.get('charge', 0):.1f} · mémoire libre {m.get('memoire_libre_pct')} % · échange {m.get('echange_pct')} % · {m.get('claude_processus')} processus Claude · {m.get('taches_programmees')} tâches programmées")
    if m.get("perso_en_cours"): info.append("passage sur un poste prêté en cours : " + ", ".join(m["perso_en_cours"]))
    if m.get("parc", {}).get("travail"): info.append(m["parc"]["travail"])
    expl = (CL.get("machines") or {}).get(k)
    F.append(f'<section class="carte {st}" id="m-{k}"><h3><span class="pt"></span>{e(TITRES.get(k, m["titre"]))}<span class="et">{e(lib)}</span></h3>'
             + (f'<p class="expl">{e(expl)}</p>' if expl else "")
             + "".join(f'<p class="info">{e(x)}</p>' for x in info)
             + "".join(f'<p class="ecart">Écart : {e(x["regle"])} — {e(x["quoi"])}</p>' for x in ecarts_par.get(k, []))
             + liste("Jobs", m["jobs"], lambda j: f'<b>{e(j["projet"])}</b> · {e(j["job"])} <span class="tag{" on" if actif(j) else ""}">{e(j["etat"])}</span>'
                     + (f' <span class="pc">{j["avancement"]} %</span>' if isinstance(j.get("avancement"), int) else ""))
             + liste("Agents permanents", m.get("agents", []), lambda a: f'{e(a["nom"])} <span class="mu">· {e(a["rythme"])}{" · Claude sur " + e(a["claude_sur"]) if a.get("claude_sur") else ""}</span>')
             + liste("Sessions", m.get("sessions", []), lambda s: f'{e(s["nom"])} <span class="mu">depuis {e(s["depuis"])}</span>')
             + liste("Services en ligne", m.get("services", []), lambda s: e(s["nom"]) + (' <span class="tag">public</span>' if s["public"] else ""))
             + "</section>")

q = datetime.fromisoformat(C["quand"])
nb_actifs = sum(1 for m in M.values() for j in m["jobs"] if actif(j))
resume = CL.get("resume") or ""
page = f'''<!doctype html><html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="refresh" content="300"><title>Carte du système</title>
<link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&family=Space+Mono:wght@400;700&display=swap" rel="stylesheet">
<style>
:root{{--bg:#123a8f;--bg2:#0d2f78;--fg:#f4f7ff;--mu:#c3d2f5;--ln:rgba(255,255,255,.17);--ac:#ffe45e;--ok:#7ee0a1;--ko:#ff8f7a;--busy:#58e6ff;--mono:"Space Mono",ui-monospace,monospace}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--fg);font:15px/1.5 "Space Grotesk",system-ui,sans-serif;
background-image:linear-gradient(rgba(255,255,255,.045) 1px,transparent 1px),linear-gradient(90deg,rgba(255,255,255,.045) 1px,transparent 1px);background-size:28px 28px}}
.wrap{{max-width:1160px;margin:0 auto;padding:32px 16px 80px}}a{{color:inherit}}
h1{{font-size:28px;margin:0}}.sous{{color:var(--mu);margin:4px 0 18px}}.nav a{{color:var(--ac);font-family:var(--mono);font-size:13px}}
.chiffres{{display:flex;flex-wrap:wrap;gap:10px;margin:14px 0}}.chiffres div{{border:1px solid var(--ln);border-radius:12px;padding:8px 14px;background:var(--bg2)}}
.chiffres b{{font-size:22px;display:block}}.ecarts{{border:1px solid var(--ko);border-radius:12px;padding:10px 16px;margin:12px 0;background:rgba(255,143,122,.08)}}
.ecarts li{{margin:3px 0}}svg{{width:100%;height:auto;margin:10px 0 18px}}
.fil{{stroke:var(--mu);stroke-width:2}}.noeud rect{{fill:var(--bg2);stroke:var(--ln);stroke-width:2}}.noeud.ok rect{{stroke:var(--ok)}}.noeud.ko rect{{stroke:var(--ko);stroke-dasharray:5 4}}
.noeud.busy rect{{stroke:var(--busy)}}.noeud.warn rect{{stroke:var(--ac)}}.noeud:hover rect{{fill:#1a4aa8}}
.t{{fill:var(--fg);font-weight:700;font-size:15px;text-anchor:middle}}.s{{fill:var(--mu);font-size:11px;text-anchor:middle;font-family:var(--mono)}}
.alerte{{fill:var(--ko)}}.leg{{fill:var(--mu);font-size:12px;font-family:var(--mono)}}
.grille{{display:grid;grid-template-columns:repeat(auto-fill,minmax(330px,1fr));gap:12px}}
.carte{{border:1px solid var(--ln);border-radius:14px;padding:12px 16px;background:var(--bg2);scroll-margin-top:12px}}
.carte h3{{margin:0 0 6px;font-size:17px;display:flex;align-items:center;gap:8px;flex-wrap:wrap}}.pt{{width:10px;height:10px;border-radius:50%;background:var(--mu)}}
.ok .pt{{background:var(--ok)}}.ko .pt{{background:var(--ko)}}.busy .pt{{background:var(--busy)}}.warn .pt{{background:var(--ac)}}
.et{{font-weight:400;color:var(--mu);font-size:13px}}.info,.mu{{color:var(--mu);font-size:13px;margin:2px 0}}.expl{{margin:4px 0;font-size:14px}}
.ecart{{color:var(--ko);font-size:13px;margin:4px 0}}details{{margin:6px 0}}summary{{cursor:pointer;color:var(--ac);font-family:var(--mono);font-size:13px}}
ul{{margin:4px 0;padding-left:18px}}li{{margin:2px 0;font-size:14px}}.tag{{font-family:var(--mono);font-size:11px;border:1px solid var(--ln);border-radius:6px;padding:0 5px;color:var(--mu)}}
.tag.on{{border-color:var(--ok);color:var(--ok)}}.pc{{font-family:var(--mono);font-size:12px;color:var(--ac)}}
:focus-visible{{outline:2px solid var(--ac);outline-offset:2px}}
</style></head><body><div class="wrap">
<p class="nav"><a href="../">← Agents permanents</a></p>
<h1>Carte du système</h1><p class="sous">Mise à jour {q.strftime("%d/%m à %H:%M")} (toutes les 15 min) · relue par Claude chaque matin à 6 h{(" — " + e(CL.get("date",""))) if CL.get("date") else ""}</p>
{f'<p class="expl">{e(resume)}</p>' if resume else ""}
<div class="chiffres"><div><b>{sum(1 for m in M.values() if m.get("en_ligne"))}</b>machines en ligne</div><div><b>{nb_actifs}</b>jobs actifs</div>
<div><b>{sum(len(m.get("agents", [])) for m in M.values())}</b>agents permanents</div><div><b>{len(M.get("vps", {}).get("sessions", []))}</b>sessions sur le VPS</div><div><b>{len(C["ecarts"])}</b>écart(s)</div></div>
{('<div class="ecarts"><b>Écarts aux règles</b><ul>' + "".join(f'<li><a href="#m-{e(x["machine"])}">{e(x["machine"])}</a> : {e(x["regle"])} — {e(x["quoi"])}</li>' for x in C["ecarts"]) + "</ul></div>") if C["ecarts"] else ""}
{"".join(S)}
<div class="grille">{"".join(F)}</div>
</div></body></html>'''
(OUT / "index.html").write_text(page, encoding="utf-8")
print("page écrite :", OUT / "index.html")
