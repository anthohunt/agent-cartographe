#!/usr/bin/env python3
"""Agent Cartographe : relevé sans IA (toutes les 15 min) de tout le système d'agents d'Anthony — machines, sessions, jobs,
agents permanents, services — et des écarts aux règles. Choix A d'Anthony (12/11/2026) ; critère : tout ce qui tourne
apparaît sur la carte avec moins de 15 min de retard, chaque écart aux règles est signalé le matin même.
Sources (lecture seule, légères) : tailscale status, registre central des jobs (maintenance/jobs.json) et registres des
sous-managers (manager-state/*-jobs.json), PARC (postes IOMEGA), fiches des agents permanents, sessions tmux et Claude du
VPS, conteneurs (docker ps, en root), crontab. Écrit etat/carte.json puis la page (page.py)."""
import glob, json, os, re, subprocess, time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
# accès root au serveur (adresse privée hors dépôt)
VPS_ROOT = os.environ.get("VPS_ROOT") or open(os.path.expanduser("~/.config/agents/vps-root")).read().strip()

ICI = Path(__file__).resolve().parent
PARIS = ZoneInfo("Europe/Paris")
# Machines et règles de l'installation : etat/machines.local.json (hors dépôt), sinon machines.exemple.json
_cf = ICI / "etat" / "machines.local.json"
CONF = json.loads((_cf if _cf.exists() else ICI / "machines.exemple.json").read_text())
NOMS_POSTES = CONF.get("noms_postes", {})
ROLES = {k: tuple(v) for k, v in CONF.get("roles", {}).items()}
REGLES = CONF.get("regles", {})
FIN_POUSSE = datetime.fromisoformat(REGLES["vps_sans_agent_jusqua"]).replace(tzinfo=PARIS) if REGLES.get("vps_sans_agent_jusqua") else None


def sh(c, t=30):
    try: return subprocess.run(c, shell=True, capture_output=True, text=True, timeout=t).stdout
    except Exception: return ""


def lire(p, defaut=None):
    try: return json.loads(Path(p).read_text())
    except Exception: return defaut


def cle_machine(texte):
    """« vr-4 », « poste IOMEGA (vr-1) », « VPS », « cloud »… → clé de machine de la carte."""
    t = (texte or "").lower()
    m = re.search(r"vr-?([1-6])", t)
    if m: return f"vr-{m[1]}"
    for k, v in NOMS_POSTES.items():
        if k.lower() in t: return v
    if "cloud" in t: return "cloud"
    if "oracle" in t: return "oracle"
    if "laptop" in t or "portable" in t: return "laptop"
    if "tour" in t: return "tour"
    if "iomega" in t or "poste" in t: return "postes"
    if "vps" in t or "srv" in t: return "vps"
    return "autre"


# Projet confidentiel : sur la carte il s'appelle seulement
# « Projet perso », sans aucune description. Les mots qui le reconnaissent sont dans etat/secret.local (hors dépôt).
try:
    SECRET = re.compile("|".join(l.strip() for l in (ICI / "etat" / "secret.local").read_text().splitlines() if l.strip()), re.I)
except OSError:
    SECRET = None
MASQUE = "Projet perso"


def secret(*x):
    return bool(SECRET and SECRET.search(json.dumps(x, ensure_ascii=False)))


def main():
    now = datetime.now(PARIS)
    M = {}
    ts = json.loads(sh("tailscale status --json") or "{}")
    for p in [ts.get("Self", {})] + list((ts.get("Peer") or {}).values()):
        h = p.get("HostName") or ""
        if not h: continue
        nom = h.replace("iomega-", "").upper() if h.lower().startswith(("iomega-i", "i6", "i7")) else h
        if nom.upper() in NOMS_POSTES:
            cle, titre, groupe = NOMS_POSTES[nom.upper()], f"{NOMS_POSTES[nom.upper()]} ({nom.upper()})", "postes"
        elif nom in ROLES:
            cle, titre = ROLES[nom]; groupe = cle if cle in ("vps", "tour", "laptop") else "reseau"
        else:
            cle, titre, groupe = h.lower(), h, ("oracle" if "oracle" in h.lower() else "reseau")
        M[cle] = {"cle": cle, "titre": titre, "groupe": groupe, "os": p.get("OS"), "en_ligne": bool(p.get("Online")),
                  "vu": (p.get("LastSeen") or "")[:16], "jobs": [], "agents": [], "sessions": [], "services": []}
    for cle, titre, groupe in (("cloud", "Sessions Claude dans le cloud (chez Anthropic, pas le VPS)", "cloud"), ("oracle", "Serveur Oracle (Paris)", "oracle")):
        M.setdefault(cle, {"cle": cle, "titre": titre, "groupe": groupe, "os": "", "en_ligne": None, "vu": "", "jobs": [], "agents": [], "sessions": [], "services": []})
    def ajoute(cle, champ, x):
        M.setdefault(cle, {"cle": cle, "titre": cle, "groupe": "reseau", "os": "", "en_ligne": None, "vu": "", "jobs": [], "agents": [], "sessions": [], "services": []})[champ].append(x)
    # jobs : registre central et registres des sous-managers
    vus = set()
    c = lire("/home/claude/maintenance/jobs.json", {})
    for j in (c.get("jobs") if isinstance(c, dict) and "jobs" in c else (list(c.values())[1] if isinstance(c, dict) and len(c) == 2 else [])) or []:
        k = cle_machine(j.get("machine")); vus.add((j.get("job") or "")[:40])
        if secret(j): j = {"projet": MASQUE, "job": MASQUE, "agent": "", "etat": "", "avancement": None}
        ajoute(k, "jobs", {"projet": j.get("projet"), "job": j.get("job"), "agent": j.get("agent"), "etat": j.get("etat"), "avancement": j.get("avancement"), "source": "registre central"})
    for f in sorted(glob.glob("/home/claude/manager-state/*-jobs.json")):
        projet = Path(f).stem.replace("-jobs", "")
        for j in lire(f, []) or []:
            if not isinstance(j, dict) or (j.get("nom") or "")[:40] in vus: continue
            k = cle_machine(j.get("poste"))
            if secret(projet, j):
                ajoute(k, "jobs", {"projet": MASQUE, "job": MASQUE, "agent": "", "etat": "", "avancement": None, "source": "registre"}); continue
            ajoute(k, "jobs", {"projet": projet, "job": j.get("nom"), "agent": j.get("poste"), "etat": j.get("etat"), "avancement": j.get("avancement"), "source": Path(f).name})
    # postes IOMEGA : qui les occupe (PARC)
    parc = json.loads(sh("python3 /home/claude/parc/parc.py etat --json", 60) or "{}")
    for p, e in parc.items():
        k = NOMS_POSTES.get(p, p)
        if k in M:
            M[k]["parc"] = {"libre": e.get("libre"), "occupe_par": e.get("occupe_par"), "travail": e.get("travail"), "depuis": e.get("depuis")}
            if secret(e.get("occupe_par"), e.get("travail")): M[k]["parc"].update({"occupe_par": MASQUE, "travail": MASQUE})
    # agents permanents (fiches du tableau)
    for a in (lire("/home/claude/agents-permanents-dash/fiches.json", {}) or {}).get("agents", []):
        mach = a.get("machine") or ""
        k = "vps" if mach.startswith("VPS") else cle_machine(mach)
        ajoute(k, "agents", {"id": a["id"], "nom": a["nom"], "rythme": a.get("rythme") or a.get("quand", "")[:60],
                             "claude_sur": "poste IOMEGA prêté" if "IOMEGA" in mach else ("tour" if "tour" in mach.lower() and not mach.startswith("VPS") else "")})
    # VPS : sessions tmux (sessions Claude), processus Claude, charge, conteneurs, crontab
    for l in sh("tmux ls -F '#{session_name}\t#{session_created}' 2>/dev/null").splitlines():
        n, _, cr = l.partition("\t")
        ajoute("vps", "sessions", {"nom": MASQUE if secret(n) else re.sub(r"^claude-(yahoo|gmail)-agents-", "", n), "depuis": datetime.fromtimestamp(int(cr or 0), PARIS).strftime("%d/%m %H:%M") if cr.isdigit() else ""})
    if "vps" in M:
        M["vps"]["charge"] = os.getloadavg()[0]
        mem = dict(re.findall(r"^(\w+):\s+(\d+)", Path("/proc/meminfo").read_text(), re.M))
        M["vps"]["memoire_libre_pct"] = round(100 * int(mem["MemAvailable"]) / int(mem["MemTotal"]))
        M["vps"]["echange_pct"] = round(100 * (1 - int(mem["SwapFree"]) / max(1, int(mem["SwapTotal"])))) if int(mem.get("SwapTotal", 0)) else 0
        M["vps"]["claude_processus"] = len([l for l in sh("ps -eo args").splitlines() if re.match(r"\S*claude(-reel/claude)?\s", l)])
        noms = set()
        for l in sh("ps -eo pid,args").splitlines():   # passages sur un poste prêté : leur nom est dans l'environnement
            pid, _, args = l.strip().partition(" ")
            if "perso-claude" in args and pid.isdigit():
                try:
                    env = Path(f"/proc/{pid}/environ").read_bytes().split(b"\0")
                    noms |= {x.split(b"=", 1)[1].decode()[:40] for x in env if x.startswith(b"PERSO_NOM=")}
                except OSError:
                    pass
        M["vps"]["perso_en_cours"] = sorted({MASQUE if secret(x) else x for x in noms})
        for l in sh("ssh -o BatchMode=yes -o ConnectTimeout=8 " + VPS_ROOT + " \"docker ps --format '{{.Names}}|{{.Ports}}'\"", 40).splitlines():
            n, _, ports = l.partition("|"); ajoute("vps", "services", {"nom": MASQUE if secret(n) else n, "public": bool(re.search(r"0\.0\.0\.0:|:::", ports))})
        M["vps"]["taches_programmees"] = len([l for l in sh("crontab -l").splitlines() if l.strip() and not l.startswith("#")])
    # écarts aux règles (déterministes ; Claude les explique la nuit)
    E = []
    def ecart(regle, machine, quoi): E.append({"regle": regle, "machine": machine, "quoi": quoi})
    actif = lambda j: re.search(r"en cours|tourne|actif|lanc", (j.get("etat") or "").lower())
    if FIN_POUSSE and now < FIN_POUSSE:
        for j in M.get("vps", {}).get("jobs", []):
            if actif(j): ecart(REGLES.get("vps_sans_agent_texte", "Aucun agent de travail sur le serveur"), "vps", f"{j['projet']} : {j['job']}")
    if "vps" in M:
        if M["vps"]["charge"] > 8: ecart("Le VPS ne doit jamais saturer", "vps", f"charge {M['vps']['charge']:.1f}")
        if M["vps"]["echange_pct"] > 80: ecart("Le VPS ne doit jamais saturer", "vps", f"mémoire d'échange pleine à {M['vps']['echange_pct']} %")
    for j in M.get("tour", {}).get("jobs", []):
        if REGLES.get("tour_motif_permis") and actif(j) and not re.search(REGLES["tour_motif_permis"], json.dumps(j, ensure_ascii=False).lower()):
            ecart(REGLES.get("tour_texte", "La tour est réservée à un usage précis"), "tour", f"{j['projet']} : {j['job']}")
    lap = [j for j in M.get("laptop", {}).get("jobs", []) if actif(j)]
    if len(lap) > REGLES.get("laptop_max", 3): ecart(f"Laptop : {REGLES.get('laptop_max', 3)} agents au maximum", "laptop", f"{len(lap)} jobs en cours")
    for k, m in M.items():
        if m.get("en_ligne") is False:
            for j in m["jobs"]:
                if actif(j): ecart("Un job en cours sur une machine éteinte ou injoignable", k, f"{j['projet']} : {j['job']}")
        if k.startswith("vr-") and m.get("parc") and not m["parc"]["libre"] and not m["jobs"] and not m["parc"].get("occupe_par"):
            ecart("Poste occupé sans job déclaré", k, "occupé, aucun job dans les registres")
    out = {"quand": now.isoformat(timespec="minutes"), "machines": M, "ecarts": E}
    if SECRET:
        def nettoie(x):
            if isinstance(x, dict): return {k: nettoie(v) for k, v in x.items()}
            if isinstance(x, list): return [nettoie(v) for v in x]
            return MASQUE if isinstance(x, str) and SECRET.search(x) else x
        out = nettoie(out)
    (ICI / "etat").mkdir(exist_ok=True)
    tmp = ICI / "etat" / "carte.json.tmp"; tmp.write_text(json.dumps(out, ensure_ascii=False, indent=1)); tmp.replace(ICI / "etat" / "carte.json")
    # historique des écarts du jour (pour le rapport du matin)
    with open(ICI / "etat" / f"ecarts-{now.date().isoformat()}.jsonl", "a") as h:
        for e in E: h.write(json.dumps({**e, "quand": out["quand"]}, ensure_ascii=False) + "\n")
    print(f"{len(M)} machines, {sum(len(m['jobs']) for m in M.values())} jobs, {len(E)} écart(s)")


if __name__ == "__main__":
    main()
