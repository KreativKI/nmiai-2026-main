#!/usr/bin/env python3
"""
CV Labeling Tool — Fast manual annotation with touch support.
Two-tap or drag to create bounding boxes. GrabCut snap for refinement.
"""

import datetime
import http.server
import json
import os
import subprocess
import traceback
import urllib.parse
from pathlib import Path

try:
    import cv2
    import numpy as np
    HAS_CV2 = True
except ImportError:
    HAS_CV2 = False

SCRIPT_DIR = Path(__file__).resolve().parent
PROGRESS_PATH = SCRIPT_DIR / "progress.json"
FOLDER_HISTORY_PATH = SCRIPT_DIR / "folder_history.json"
HTML_PATH = SCRIPT_DIR / "index.html"

PORT = 8787
MAX_FOLDER_HISTORY = 10
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
CONTENT_TYPES = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp"}


def load_json(path):
    path = Path(path)
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return {}


def save_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def add_folder_history(folder):
    history = load_json(FOLDER_HISTORY_PATH)
    folders = history.get("folders", [])
    if folder in folders:
        folders.remove(folder)
    folders.insert(0, folder)
    save_json(FOLDER_HISTORY_PATH, {"folders": folders[:MAX_FOLDER_HISTORY]})


def scan_folder(folder_path):
    folder = Path(folder_path)
    if not folder.is_dir():
        return {}, [], folder, folder / "labels"
    images_subdir = folder / "images"
    images_dir = images_subdir if images_subdir.is_dir() else folder
    labels_dir = folder / "labels"
    manifest_path = folder / "manifest.json"
    if manifest_path.exists():
        manifest = load_json(manifest_path)
        return manifest, sorted(manifest.keys()), images_dir, labels_dir
    images = sorted(
        f.name for f in images_dir.iterdir()
        if f.suffix.lower() in IMAGE_EXTENSIONS and "_bound" not in f.stem
    )
    manifest = {name: {"category_id": 0, "product_name": Path(name).stem} for name in images}
    return manifest, images, images_dir, labels_dir


def apply_folder(folder_path):
    manifest, image_list, images_dir, labels_dir = scan_folder(folder_path)
    labels_dir.mkdir(exist_ok=True)
    LabelHandler.manifest = manifest
    LabelHandler.image_list = image_list
    LabelHandler.images_dir = images_dir
    LabelHandler.labels_dir = labels_dir
    return len(image_list)


def get_saved_bbox(labels_dir, filename):
    label_path = Path(labels_dir) / (Path(filename).stem + ".txt")
    if not label_path.exists():
        return None
    try:
        parts = label_path.read_text().strip().split()
        if len(parts) >= 5:
            w, h = float(parts[3]), float(parts[4])
            if w < 0.01 or h < 0.01:
                return None
            return {"cx": float(parts[1]), "cy": float(parts[2]), "w": w, "h": h}
    except (ValueError, IndexError):
        pass
    return None


def run_grabcut(img_path, bbox_norm, mode="all"):
    if not HAS_CV2:
        return {"error": "OpenCV not available"}
    img = cv2.imread(img_path)
    if img is None:
        return {"error": "Could not read image"}
    max_dim = 480
    oh, ow = img.shape[:2]
    if max(ow, oh) > max_dim:
        s = max_dim / max(ow, oh)
        img = cv2.resize(img, (int(ow * s), int(oh * s)))
    h, w = img.shape[:2]
    bx = max(1, int((bbox_norm["cx"] - bbox_norm["w"] / 2) * w))
    by = max(1, int((bbox_norm["cy"] - bbox_norm["h"] / 2) * h))
    bw = min(w - bx - 1, int(bbox_norm["w"] * w))
    bh = min(h - by - 1, int(bbox_norm["h"] * h))
    if bw < 10 or bh < 10:
        return {"error": "Box too small"}
    mask = np.zeros((h, w), np.uint8)
    bgd, fgd = np.zeros((1, 65), np.float64), np.zeros((1, 65), np.float64)
    try:
        cv2.grabCut(img, mask, (bx, by, bw, bh), bgd, fgd, 2, cv2.GC_INIT_WITH_RECT)
    except cv2.error:
        return {"error": "GrabCut failed"}
    fg = np.where((mask == cv2.GC_FGD) | (mask == cv2.GC_PR_FGD), 1, 0).astype(np.uint8)
    coords = cv2.findNonZero(fg)
    if coords is None:
        return {"error": "No foreground found"}
    rx, ry, rw, rh = cv2.boundingRect(coords)
    pad = int(max(rw, rh) * 0.02)
    new_rx = max(0, rx - pad)
    new_ry = max(0, ry - pad)
    new_rw = min(w - new_rx, rw + 2 * pad)
    new_rh = min(h - new_ry, rh + 2 * pad)
    if mode == "tb":
        return {"ok": True, "bbox": {
            "cx": bbox_norm["cx"],
            "cy": round((new_ry + new_rh / 2) / h, 6),
            "w": bbox_norm["w"],
            "h": round(new_rh / h, 6),
        }}
    return {"ok": True, "bbox": {
        "cx": round((new_rx + new_rw / 2) / w, 6),
        "cy": round((new_ry + new_rh / 2) / h, 6),
        "w": round(new_rw / w, 6),
        "h": round(new_rh / h, 6),
    }}


class LabelHandler(http.server.BaseHTTPRequestHandler):
    manifest = {}
    image_list = []
    images_dir = None
    labels_dir = None

    def log_message(self, fmt, *args):
        msg = str(args[0]) if args else ""
        if "/api/" in msg or ".jpg" in msg or ".png" in msg:
            return
        super().log_message(fmt, *args)

    def send_json(self, data, status=200):
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def serve_file(self, filepath, content_type):
        filepath = Path(filepath)
        if not filepath.exists():
            self.send_error(404)
            return
        data = filepath.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(data)

    def read_body(self):
        length = int(self.headers.get("Content-Length", 0))
        if length == 0:
            return {}
        try:
            return json.loads(self.rfile.read(length))
        except (json.JSONDecodeError, ValueError):
            return None

    def image_data(self, img_name, index):
        info = self.manifest.get(img_name, {"category_id": 0, "product_name": img_name})
        saved_bbox = get_saved_bbox(self.labels_dir, img_name) if self.labels_dir else None
        return {
            "filename": img_name,
            "index": index,
            "category_id": info.get("category_id", 0),
            "product_name": info.get("product_name", img_name),
            "image_url": f"/images/{urllib.parse.quote(img_name)}",
            "bbox": saved_bbox,
            "has_label": saved_bbox is not None,
        }

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        path = urllib.parse.urlparse(self.path).path

        if path in ("/", "/index.html"):
            self.serve_file(HTML_PATH, "text/html")
            return

        if path == "/api/config":
            progress = load_json(PROGRESS_PATH)
            history = load_json(FOLDER_HISTORY_PATH)
            self.send_json({
                "folder": progress.get("folder", ""),
                "has_folder": bool(progress.get("folder")),
                "folder_history": history.get("folders", []),
            })
            return

        if path == "/api/browse":
            try:
                result = subprocess.run(
                    ["osascript", "-e", 'set theFolder to POSIX path of (choose folder with prompt "Select image folder")'],
                    capture_output=True, text=True, timeout=120,
                )
                folder = result.stdout.strip()
                if result.returncode == 0 and folder:
                    self.send_json({"folder": folder})
                else:
                    self.send_json({"folder": "", "cancelled": True})
            except subprocess.TimeoutExpired:
                self.send_json({"folder": "", "cancelled": True})
            return

        if path == "/api/list-dir":
            qs = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            dir_path = qs.get("path", ["/Volumes"])[0]
            p = Path(dir_path)
            if not p.is_dir():
                self.send_json({"error": "Not a directory"}, 400)
                return
            entries = []
            try:
                for item in sorted(p.iterdir()):
                    if item.name.startswith("."):
                        continue
                    if item.is_dir():
                        has_images = any(
                            f.suffix.lower() in IMAGE_EXTENSIONS
                            for f in (item / "images" if (item / "images").is_dir() else item).iterdir()
                            if f.is_file()
                        ) if item.is_dir() else False
                        entries.append({"name": item.name, "path": str(item), "type": "dir", "has_images": has_images})
            except PermissionError:
                pass
            self.send_json({"path": str(p), "parent": str(p.parent), "entries": entries})
            return

        if path == "/api/status":
            progress = load_json(PROGRESS_PATH)
            total = len(self.image_list)
            labeled = len(progress.get("labeled", []))
            skipped = len(progress.get("skipped", []))
            self.send_json({
                "total": total,
                "labeled": labeled,
                "skipped": skipped,
                "remaining": total - labeled - skipped,
                "folder": progress.get("folder", ""),
            })
            return

        if path == "/api/list":
            progress = load_json(PROGRESS_PATH)
            labeled_set = set(progress.get("labeled", []))
            skipped_set = set(progress.get("skipped", []))
            items = []
            for i, img_name in enumerate(self.image_list):
                status = "labeled" if img_name in labeled_set else "skipped" if img_name in skipped_set else "pending"
                info = self.manifest.get(img_name, {"product_name": img_name})
                items.append({
                    "index": i, "filename": img_name,
                    "product_name": info.get("product_name", img_name),
                    "status": status,
                })
            self.send_json(items)
            return

        if path == "/api/next":
            progress = load_json(PROGRESS_PATH)
            done = set(progress.get("labeled", []) + progress.get("skipped", []))
            for i, img in enumerate(self.image_list):
                if img not in done:
                    self.send_json(self.image_data(img, i))
                    return
            self.send_json({"filename": None, "done": True})
            return

        if path == "/api/goto":
            qs = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            idx = int(qs.get("index", [0])[0])
            if 0 <= idx < len(self.image_list):
                self.send_json(self.image_data(self.image_list[idx], idx))
            else:
                self.send_json({"error": "Index out of range"}, 400)
            return

        if path.startswith("/images/") and self.images_dir:
            img_name = urllib.parse.unquote(path[len("/images/"):])
            resolved = (self.images_dir / img_name).resolve()
            if not str(resolved).startswith(str(self.images_dir.resolve())):
                self.send_error(403)
                return
            ct = CONTENT_TYPES.get(resolved.suffix.lower(), "application/octet-stream")
            self.serve_file(resolved, ct)
            return

        self.send_error(404)

    def do_POST(self):
        path = urllib.parse.urlparse(self.path).path
        body = self.read_body()
        if body is None:
            self.send_json({"error": "Invalid JSON"}, 400)
            return
        try:
            return self._handle_post(path, body)
        except (KeyError, TypeError) as e:
            self.send_json({"error": f"Missing field: {e}"}, 400)

    def _handle_post(self, path, body):
        if path == "/api/set-folder":
            folder = body["folder"].strip().rstrip("/")
            folder_path = Path(folder)
            if not folder_path.is_dir():
                self.send_json({"error": f"Not a valid folder: {folder}"}, 400)
                return
            total = apply_folder(folder_path)
            progress = load_json(PROGRESS_PATH)
            if progress.get("folder") != folder:
                progress = {"folder": folder, "labeled": [], "skipped": []}
            save_json(PROGRESS_PATH, progress)
            add_folder_history(folder)
            print(f"Folder: {folder} ({total} images)")
            self.send_json({"ok": True, "total": total, "folder": folder})
            return

        if path == "/api/label":
            if not self.labels_dir:
                self.send_json({"error": "No folder selected"}, 400)
                return
            filename = body["filename"]
            bbox = body["bbox"]
            category_id = body["category_id"]
            label_name = Path(filename).stem + ".txt"
            label_path = self.labels_dir / label_name
            line = f"{category_id} {bbox['cx']:.6f} {bbox['cy']:.6f} {bbox['w']:.6f} {bbox['h']:.6f}\n"
            with open(label_path, "w") as f:
                f.write(line)
            progress = load_json(PROGRESS_PATH)
            labeled = progress.get("labeled", [])
            skipped = progress.get("skipped", [])
            if filename not in labeled:
                labeled.append(filename)
            if filename in skipped:
                skipped.remove(filename)
            progress["labeled"] = labeled
            progress["skipped"] = skipped
            save_json(PROGRESS_PATH, progress)
            # Auto-notify CV agent when running low
            remaining = len(self.image_list) - len(labeled) - len(skipped)
            if remaining <= 20:
                notify_path = SCRIPT_DIR.parent.parent.parent / "intelligence" / "for-cv-agent" / "NEED-MORE-IMAGES.md"
                if not notify_path.exists():
                    notify_path.parent.mkdir(parents=True, exist_ok=True)
                    notify_path.write_text(
                        f"---\npriority: HIGH\nfrom: ops-agent\ntimestamp: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}\n---\n\n"
                        f"## Need More Images\n\nJC has {remaining} images left in the current batch.\n"
                        f"Current folder: {progress.get('folder', 'unknown')}\n"
                        f"Labeled: {len(labeled)} | Remaining: {remaining}\n\n"
                        f"Please download the next batch from GCP and place in label_batches/batch_NNN/.\n"
                    )
                    print(f"AUTO-NOTIFY: {remaining} images remaining, notified CV agent")
            self.send_json({"ok": True, "saved": str(label_path)})
            return

        if path == "/api/skip":
            filename = body["filename"]
            progress = load_json(PROGRESS_PATH)
            skipped = progress.get("skipped", [])
            if filename not in skipped:
                skipped.append(filename)
            progress["skipped"] = skipped
            save_json(PROGRESS_PATH, progress)
            self.send_json({"ok": True})
            return

        if path == "/api/complete-batch":
            progress = load_json(PROGRESS_PATH)
            folder = progress.get("folder", "")
            labeled = progress.get("labeled", [])
            total = len(self.image_list)

            # Write completion notice to CV agent
            intel_dir = SCRIPT_DIR.parent.parent.parent / "intelligence" / "for-cv-agent"
            intel_dir.mkdir(parents=True, exist_ok=True)
            batch_name = Path(folder).name if folder else "unknown"
            notice_path = intel_dir / "BATCH-LABELED.md"
            notice_path.write_text(
                f"---\npriority: HIGH\nfrom: ops-agent\ntimestamp: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}\n---\n\n"
                f"## Batch Labeled Complete\n\n"
                f"**Batch:** {batch_name}\n"
                f"**Folder:** {folder}\n"
                f"**Labeled:** {len(labeled)} / {total}\n"
                f"**Labels location:** {folder}/labels/\n"
                f"**Format:** YOLO .txt (category_id cx cy w h, normalized 0-1)\n\n"
                f"Please verify labels and prepare for training.\n"
            )
            print(f"BATCH COMPLETE: {batch_name} ({len(labeled)}/{total}), notified CV agent")

            # Find next batch
            batch_dir = Path(folder).parent if folder else None
            next_batch = None
            if batch_dir and batch_dir.is_dir():
                batches = sorted(d.name for d in batch_dir.iterdir() if d.is_dir() and d.name.startswith("batch_"))
                current_idx = batches.index(batch_name) if batch_name in batches else -1
                if current_idx >= 0 and current_idx + 1 < len(batches):
                    next_batch = str(batch_dir / batches[current_idx + 1])

            self.send_json({
                "ok": True,
                "batch": batch_name,
                "labeled": len(labeled),
                "total": total,
                "next_batch": next_batch,
            })
            return

        if path == "/api/load-next-batch":
            next_folder = body.get("folder", "")
            if not next_folder or not Path(next_folder).is_dir():
                self.send_json({"error": "Next batch folder not found"}, 400)
                return
            total = apply_folder(next_folder)
            progress = {"folder": next_folder, "labeled": [], "skipped": []}
            save_json(PROGRESS_PATH, progress)
            add_folder_history(next_folder)
            print(f"Next batch: {next_folder} ({total} images)")
            self.send_json({"ok": True, "total": total, "folder": next_folder})
            return

        if path == "/api/grabcut":
            if not HAS_CV2 or not self.images_dir:
                self.send_json({"error": "Not available"}, 400)
                return
            img_path = self.images_dir / body["filename"]
            if not img_path.exists():
                self.send_json({"error": "Image not found"}, 404)
                return
            result = run_grabcut(str(img_path), body["bbox"], body.get("mode", "all"))
            self.send_json(result)
            return

        self.send_error(404)


def main():
    progress = load_json(PROGRESS_PATH)
    saved_folder = progress.get("folder", "")
    if saved_folder and Path(saved_folder).is_dir():
        total = apply_folder(saved_folder)
        labeled = len(progress.get("labeled", []))
        print(f"=== CV Labeler ===")
        print(f"Folder:  {saved_folder}")
        print(f"Images:  {total} ({labeled} labeled)")
    else:
        print("=== CV Labeler ===")
        print("No folder selected.")

    import socket
    ip = socket.gethostbyname(socket.gethostname())
    print(f"\nLocal:  http://localhost:{PORT}")
    print(f"iPad:   http://{ip}:{PORT}")
    print("Ctrl+C to stop\n")

    server = http.server.HTTPServer(("0.0.0.0", PORT), LabelHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
        server.shutdown()


if __name__ == "__main__":
    main()
