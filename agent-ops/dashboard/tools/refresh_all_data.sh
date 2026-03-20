#!/bin/bash
# Refresh all dashboard data from sources.
# Run manually or on a cron: ./tools/refresh_all_data.sh
# Data files are written to public/data/ — the Vite dev server serves them live.

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DASH_DIR="$(dirname "$SCRIPT_DIR")"
DATA_DIR="$DASH_DIR/public/data"
SHARED_TOOLS="$DASH_DIR/../../shared/tools"

echo "=== Dashboard Data Refresh $(date '+%H:%M:%S') ==="

# 1. Copy fresh ML viz data
ML_DATA="$DASH_DIR/../../agent-ml/solutions/data/viz_data.json"
if [ -f "$ML_DATA" ]; then
    cp "$ML_DATA" "$DATA_DIR/viz_data.json"
    echo "[OK] ML viz_data.json refreshed"
else
    echo "[--] ML viz_data.json not found"
fi

# 2. Pull CV training logs from GCP VM
echo "[..] Pulling CV training logs from GCP..."
CV_RESULTS=$(gcloud compute ssh cv-train-1 --zone=europe-west1-c --project=ai-nm26osl-1779 --command="cat /home/jcfrugaard/cv-train/models/yolo11m_ng/results.csv 2>/dev/null" 2>/dev/null)
if [ -n "$CV_RESULTS" ]; then
    python3 -c "
import csv, json, io
entries = []
for model_name, path_suffix in [('yolo11m', 'yolo11m_ng'), ('yolo26m', 'yolo26m_ng')]:
    import subprocess
    result = subprocess.run(
        ['gcloud', 'compute', 'ssh', 'cv-train-1', '--zone=europe-west1-c',
         '--project=ai-nm26osl-1779',
         '--command=cat /home/jcfrugaard/cv-train/models/' + path_suffix + '/results.csv 2>/dev/null'],
        capture_output=True, text=True, timeout=20
    )
    if result.returncode == 0 and result.stdout.strip():
        reader = csv.DictReader(io.StringIO(result.stdout))
        for row in reader:
            row = {k.strip(): v.strip() for k, v in row.items()}
            entries.append({
                'epoch': int(row.get('epoch', 0)),
                'model': model_name,
                'mAP50': float(row.get('metrics/mAP50(B)', 0)),
                'mAP5095': float(row.get('metrics/mAP50-95(B)', 0)),
                'precision': float(row.get('metrics/precision(B)', 0)),
                'recall': float(row.get('metrics/recall(B)', 0)),
                'box_loss': float(row.get('train/box_loss', 0)),
                'cls_loss': float(row.get('train/cls_loss', 0)),
            })
with open('$DATA_DIR/cv_training_log.json', 'w') as f:
    json.dump(entries, f, indent=2)
print(f'[OK] CV training log: {len(entries)} entries')
" 2>/dev/null || echo "[!!] CV training log pull failed"
else
    echo "[--] CV VM not reachable or no results"
fi

# 3. Fetch NLP task logs from Cloud Run
echo "[..] Fetching NLP Cloud Run logs..."
python3 "$DASH_DIR/tools/fetch_nlp_logs.py" 2>/dev/null && echo "[OK] NLP task logs refreshed" || echo "[!!] NLP log fetch failed"

# 4. Check NLP endpoint health
python3 "$SHARED_TOOLS/check_nlp_endpoint.py" --json > "$DATA_DIR/nlp_health.json" 2>/dev/null && echo "[OK] NLP health check saved" || echo "[!!] NLP health check failed"

echo "=== Refresh complete ==="
