#!/bin/bash
# Cartographe : relevé sans IA + page, toutes les 15 min (léger : ~1 s)
cd "$(dirname "$0")" && mkdir -p logs etat && python3 releve.py >> logs/releve.log 2>&1 && python3 page.py >/dev/null 2>> logs/releve.log
find etat -name 'ecarts-*.jsonl' -mtime +14 -delete 2>/dev/null; tail -n 2000 logs/releve.log > logs/releve.tmp && mv logs/releve.tmp logs/releve.log
