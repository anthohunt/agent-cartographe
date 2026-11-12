#!/bin/bash
# Agent Cartographe : relecture de Claude chaque matin à 6 h (heure de Paris), avant le rapport du matin ; sur un poste IOMEGA
# prêté (perso-claude, sans trace), dans la file des agents du site. Écrit etat/claude.json (lu par la page) et dépose la
# partie « cartographe » du rapport du matin. Usage : nuit.sh   (FORCE=1 : hors heure)
set -u
R=$(cd "$(dirname "$0")" && pwd); J=$(TZ=Europe/Paris date +%F)
[ "${FORCE:-0}" = 1 ] || case "$(TZ=Europe/Paris date +%H)" in 06|07) ;; *) exit 0;; esac
mkdir -p "$R/logs" "$R/verrous"; chmod 700 "$R/verrous"
[ "${FORCE:-0}" = 1 ] || [ ! -e "$R/logs/$J.fait" ] || exit 0
exec 9>"$R/verrous/nuit.lock"; flock -n 9 || exit 1
exec 8>/tmp/agents-site.lock; flock -w 2400 8 || exit 6
L="$R/logs/$J.log"; log() { echo "$(date -u +%FT%TZ) $*" >> "$L"; }
python3 "$R/releve.py" >> "$L" 2>&1
W=/home/claude/agent-cartographe-passe; rm -rf "$W"; mkdir -p "$W/sortie"
cp "$R/etat/carte.json" "$W/"
python3 "$R/ecarts-jour.py" "$J" > "$W/ecarts-jour.json" 2>> "$L"
{ [ -s "$R/etat/regles.local.md" ] && cp "$R/etat/regles.local.md" "$W/regles.md" || cp "$R/regles.exemple.md" "$W/regles.md"; }; cp "$R/etat/claude.json" "$W/hier.json" 2>/dev/null || echo '{}' > "$W/hier.json"
export DATE="$J"; perl -pe 's/\{\{(\w+)\}\}/$ENV{$1}/g' "$R/consigne.md" > "$R/logs/$J.consigne.md"
CPT=$(/usr/local/bin/compte-agents 2>/dev/null | tr -d "[:space:]"); CPT=${CPT:-$(cat /home/claude/maintenance/compte-actif)}
TOKF=/home/claude/.claude-tokens/account-$CPT.env; CFG=/home/claude/.claude-$CPT-iomega; mkdir -p "$CFG"
[ -s "$TOKF" ] || { log "compte $CPT sans jeton"; exit 1; }
log "claude (compte $CPT)"
( cd "$W" && env -u ANTHROPIC_API_KEY -u CLAUDECODE CLAUDE_CONFIG_DIR="$CFG" \
    CLAUDE_CODE_OAUTH_TOKEN="$(grep -oP '(?<=CLAUDE_CODE_OAUTH_TOKEN=).*' "$TOKF" | tr -d "\"'")" PERSO_NOM=cartographe \
    timeout 40m /home/claude/perso-iomega/perso-claude -p "$(cat "$R/logs/$J.consigne.md")" --model claude-opus-5-5 --effort medium \
    --allowedTools "Read" "Edit(/sortie/claude.json)" "Write(/sortie/claude.json)" --disallowedTools "Bash" "WebFetch" "WebSearch" < /dev/null ) >> "$L" 2>&1
RC=$?; log "claude fini : code $RC"
[ "$RC" = 75 ] && { log "aucun poste libre : nouvel essai au cron suivant"; rm -rf "$W"; exit 6; }
if python3 -c "import json,sys;json.load(open(sys.argv[1]))" "$W/sortie/claude.json" 2>/dev/null; then
  cp "$W/sortie/claude.json" "$R/etat/claude.json"; log "relecture enregistrée"
else log "relecture absente ou illisible : le rapport ne porte que les écarts du programme"; fi
rm -rf "$W"
python3 "$R/page.py" >> "$L" 2>&1
python3 "$R/deposer.py" "$J" >> "$L" 2>&1 && touch "$R/logs/$J.fait"
