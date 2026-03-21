#!/usr/bin/env python3
"""
CV Labeling Tool — Local HTTP Server
Serves images, loads Grounding DINO pre-detections, saves YOLO-format labels.
Zero dependencies beyond Python stdlib.
"""

import http.server
import json
import urllib.parse
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
AGENT_CV = SCRIPT_DIR.parent.parent
SYNTHETIC = AGENT_CV / "synthetic_shelf"
IMAGES_DIR = SYNTHETIC / "images"
LABELS_DIR = SYNTHETIC / "labels"
REFERENCES_DIR = SYNTHETIC / "references"
MANIFEST_PATH = SYNTHETIC / "manifest.json"
PREDETECTIONS_PATH = SYNTHETIC / "pre_detections.json"
AUTO_LABEL_QUEUE_PATH = SCRIPT_DIR / "auto_label_queue.json"
PROGRESS_PATH = SCRIPT_DIR / "progress.json"
HTML_PATH = SCRIPT_DIR / "index.html"

PORT = 8787


def load_json(path):
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return {}


def save_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def get_reference_url(info):
    """Return URL for reference photo if it exists."""
    ref_name = info.get("reference_image")
    if ref_name and (REFERENCES_DIR / ref_name).exists():
        return f"/references/{urllib.parse.quote(ref_name)}"
    return None


CONTENT_TYPES = {
    ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
    ".png": "image/png", ".webp": "image/webp",
}


def serve_asset(handler, prefix, base_dir, path):
    name = urllib.parse.unquote(path[len(prefix):])
    resolved = (base_dir / name).resolve()
    if not str(resolved).startswith(str(base_dir.resolve())):
        handler.send_error(403)
        return
    ct = CONTENT_TYPES.get(resolved.suffix.lower(), "application/octet-stream")
    handler.serve_file(resolved, ct)


class LabelHandler(http.server.BaseHTTPRequestHandler):
    manifest = {}
    predetections = {}
    progress = {}
    image_list = []

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

    def image_data(self, img, index):
        info = self.manifest[img]
        return {
            "filename": img,
            "index": index,
            "category_id": info["category_id"],
            "product_name": info["product_name"],
            "image_url": f"/images/{urllib.parse.quote(img)}",
            "suggested_bbox": self.predetections.get(img),
            "reference_url": get_reference_url(info),
        }

    def do_GET(self):
        path = urllib.parse.urlparse(self.path).path

        if path in ("/", "/index.html"):
            self.serve_file(HTML_PATH, "text/html")
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
            })
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

        if path == "/api/list":
            progress = load_json(PROGRESS_PATH)
            labeled_set = set(progress.get("labeled", []))
            skipped_set = set(progress.get("skipped", []))
            items = []
            for i, img in enumerate(self.image_list):
                if img in labeled_set:
                    status = "labeled"
                elif img in skipped_set:
                    status = "skipped"
                else:
                    status = "pending"
                items.append({
                    "index": i,
                    "filename": img,
                    "product_name": self.manifest[img]["product_name"],
                    "status": status,
                })
            self.send_json(items)
            return

        if path.startswith("/images/"):
            serve_asset(self, "/images/", IMAGES_DIR, path)
            return

        if path.startswith("/references/"):
            serve_asset(self, "/references/", REFERENCES_DIR, path)
            return

        if path == "/api/goto":
            qs = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            idx = int(qs.get("index", [0])[0])
            if 0 <= idx < len(self.image_list):
                self.send_json(self.image_data(self.image_list[idx], idx))
            else:
                self.send_json({"error": "Index out of range"}, 400)
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
        if path == "/api/label":
            filename = body["filename"]
            bbox = body["bbox"]
            category_id = body["category_id"]

            label_name = Path(filename).stem + ".txt"
            label_path = LABELS_DIR / label_name
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

        if path == "/api/auto-label":
            queue = load_json(AUTO_LABEL_QUEUE_PATH)
            queue.setdefault("queue", []).append({
                "filename": body["filename"],
                "category_id": body["category_id"],
                "bbox": body["bbox"],
            })
            save_json(AUTO_LABEL_QUEUE_PATH, queue)
            self.send_json({"ok": True, "queued": len(queue["queue"])})
            return

        self.send_error(404)


def main():
    LABELS_DIR.mkdir(parents=True, exist_ok=True)

    if not MANIFEST_PATH.exists():
        print(f"ERROR: No manifest.json at {MANIFEST_PATH}")
        print("Run generate_manifest.py first, or create manually.")
        print("Format: {\"filename.jpg\": {\"category_id\": 42, \"product_name\": \"Tine Melk\"}}")
        raise SystemExit(1)

    manifest = load_json(MANIFEST_PATH)
    predetections = load_json(PREDETECTIONS_PATH)
    progress = load_json(PROGRESS_PATH)

    LabelHandler.manifest = manifest
    LabelHandler.predetections = predetections
    LabelHandler.image_list = sorted(manifest.keys())

    total = len(LabelHandler.image_list)
    labeled = len(progress.get("labeled", []))
    skipped = len(progress.get("skipped", []))

    print("=== CV Labeling Tool ===")
    print(f"Images:    {IMAGES_DIR}")
    print(f"Labels:    {LABELS_DIR}")
    print(f"Total:     {total}")
    print(f"Labeled:   {labeled}")
    print(f"Skipped:   {skipped}")
    print(f"Remaining: {total - labeled - skipped}")
    if predetections:
        print(f"Pre-detections: {len(predetections)} loaded")
    else:
        print("Pre-detections: none (using centered default box)")
    print(f"\nOpen http://localhost:{PORT}")
    print("Ctrl+C to stop\n")

    server = http.server.HTTPServer(("127.0.0.1", PORT), LabelHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
        server.shutdown()


if __name__ == "__main__":
    main()
