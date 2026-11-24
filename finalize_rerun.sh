#!/usr/bin/env bash
# Waits for rerun_o2_h2o2.py (tmux: evtol_rerun) to finish, then regenerates the
# LaTeX tables and SVG plots from the fresh CSVs. Self-contained: run detached in
# its own tmux session so it survives the window closing.
set -u
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUN_LOG="$DIR/results/rerun_o2_h2o2.log"
FIN_LOG="$DIR/results/finalize.log"
# Python from the evtol-py3.9 conda env; override with PY_CONDA=/path/to/python
PY_CONDA="${PY_CONDA:-python}"
cd "$DIR" || exit 1

log() { echo "[$(date '+%F %T')] $*" | tee -a "$FIN_LOG"; }

: > "$FIN_LOG"
log "Watcher started; waiting for run to finish (EXIT_CODE marker in run log)..."

# Wait until the runner writes its EXIT_CODE marker.
while ! grep -q 'EXIT_CODE=' "$RUN_LOG" 2>/dev/null; do
    sleep 30
done

CODE=$(grep -oE 'EXIT_CODE=[0-9]+' "$RUN_LOG" | tail -1 | cut -d= -f2)
log "Run finished with EXIT_CODE=$CODE"

O2_ROWS=$(($(wc -l < results/exp0_O2.csv) - 1))
H_ROWS=$(($(wc -l < results/exp0_O2H2.csv) - 1))
log "Data rows: exp0_O2.csv=$O2_ROWS  exp0_O2H2.csv=$H_ROWS (expect 30 each)"

if [ "$CODE" != "0" ] || [ "$O2_ROWS" -lt 30 ] || [ "$H_ROWS" -lt 30 ]; then
    log "Run incomplete or failed -- NOT regenerating tables/plots. Inspect $RUN_LOG."
    exit 1
fi

log "Regenerating tables (make_tables.py)..."
python3 make_tables.py >> "$FIN_LOG" 2>&1 && log "tables OK" || log "tables FAILED"

log "Regenerating plots (make_plots.py)..."
PYTHONPATH="$DIR" "$PY_CONDA" make_plots.py >> "$FIN_LOG" 2>&1 && log "plots OK" || log "plots FAILED"

# quick sanity summary: any TO left in the two re-run configs?
O2_TO=$(grep -c ',TO,' results/exp0_O2.csv || true)
H_TO=$(grep -c ',TO,' results/exp0_O2H2.csv || true)
log "Remaining TO rows: O2=$O2_TO  O2H2=$H_TO"
log "FINALIZE DONE. Artifacts: results/table1.tex, results/table2.tex, results/{profit,run_time,service_rate}.svg"
