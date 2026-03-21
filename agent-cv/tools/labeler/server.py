#!/usr/bin/env python3
"""
CV Track Image Labeling Tool — Local HTTP Server
Serves images and saves YOLO-format bounding box labels.
No dependencies beyond Python stdlib.
"""

import http.server
import json
import os
import sys
import urllib.parse
from pathlib import Path

# Paths
SCRIPT_DIR = Path(__file__).resolve().parent
AGENT_CV = SCRIPT_DIR.parent.parent
SYNTHETIC = AGENT_CV / "synthetic_shelf"
IMAGES_DIR = SYNTHETIC / "images"
LABELS_DIR = SYNTHETIC / "labels"
MANIFEST_PATH = SYNTHETIC / "manifest.json"
PROGRESS_PATH = SCRIPT_DIR / "progress.json"
HTML_PATH = SCRIPT_DIR / "index.html"

PORT = 8787


def load_manifest():
    if not MANIFEST_PATH.exists():
        print(f"ERROR: manifest.json not found at {MANIFEST_PATH}")
        print("Create it with: {{filename: {{category_id: int, product_name: str}}}}")
        sys.exit(1)
    with open(MANIFEST_PATH) as f:
        return json.load(f)


def load_progress():
    if PROGRESS_PATH.exists():
        with open(PROGRESS_PATH) as f:
            return json.load(f)
    return {"labeled": [], "skipped": []}


def save_progress(progress):
    with open(PROGRESS_PATH, "w") as f:
        json.dump(progress, f, indent=2)


class LabelHandler(http.server.BaseHTTPRequestHandler):
    manifest = None
    progress = None
    image_list = None

    def log_message(self, format, *args):
        # Quieter logging
        if "/api/" in str(args[0]) if args else False:
            return
        super().log_message(format, *args)

    def send_json(self, data, status=200):
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path == "/" or path == "/index.html":
            self._serve_file(HTML_PATH, "text/html")

        elif path == "/api/status":
            progress = load_progress()
            total = len(LabelHandler.image_list)
            labeled = len(progress["labeled"])
            skipped = len(progress["skipped"])
            remaining = total - labeled - skipped
            self.send_json({
                "total": total,
                "labeled": labeled,
                "skipped": skipped,
                "remaining": remaining,
            })

        elif path == "/api/next":
            progress = load_progress()
            done = set(progress["labeled"] + progress["skipped"])
            for img in LabelHandler.image_list:
                if img not in done:
                    info = LabelHandler.manifest[img]
                    self.send_json({
                        "filename": img,
                        "category_id": info["category_id"],
                        "product_name": info["product_name"],
                        "image_url": f"/images/{urllib.parse.quote(img)}",
                    })
                    return
            self.send_json({"filename": None, "done": True})

        elif path.startswith("/images/"):
            img_name = urllib.parse.unquote(path[len("/images/"):])
            img_path = IMAGES_DIR / img_name
            if img_path.exists():
                ext = img_path.suffix.lower()
                ct = {
                    ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
                    ".png": "image/png", ".webp": "image/webp",
                }.get(ext, "application/octet-stream")
                self._serve_file(img_path, ct)
            else:
                self.send_error(404)

        else:
            self.send_error(404)

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        content_len = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(content_len)) if content_len > 0 else {}

        if path == "/api/label":
            filename = body["filename"]
            bbox = body["bbox"]  # {cx, cy, w, h} normalized 0-1
            category_id = body["category_id"]

            # Save YOLO format label
            label_name = Path(filename).stem + ".txt"
            label_path = LABELS_DIR / label_name
            line = f"{category_id} {bbox['cx']:.6f} {bbox['cy']:.6f} {bbox['w']:.6f} {bbox['h']:.6f}\n"
            with open(label_path, "w") as f:
                f.write(line)

            # Update progress
            progress = load_progress()
            if filename not in progress["labeled"]:
                progress["labeled"].append(filename)
            # Remove from skipped if previously skipped
            if filename in progress["skipped"]:
                progress["skipped"].remove(filename)
            save_progress(progress)

            self.send_json({"ok": True, "saved": str(label_path)})

        elif path == "/api/skip":
            filename = body["filename"]
            progress = load_progress()
            if filename not in progress["skipped"]:
                progress["skipped"].append(filename)
            save_progress(progress)
            self.send_json({"ok": True})

        elif path == "/api/goto":
            # Jump to a specific index
            index = body.get("index", 0)
            progress = load_progress()
            if 0 <= index < len(LabelHandler.image_list):
                img = LabelHandler.image_list[index]
                info = LabelHandler.manifest[img]
                self.send_json({
                    "filename": img,
                    "category_id": info["category_id"],
                    "product_name": info["product_name"],
                    "image_url": f"/images/{urllib.parse.quote(img)}",
                    "index": index,
                })
            else:
                self.send_json({"error": "Index out of range"}, 400)

        else:
            self.send_error(404)

    def _serve_file(self, filepath, content_type):
        filepath = Path(filepath)
        if not filepath.exists():
            self.send_error(404)
            return
        data = filepath.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def main():
    LABELS_DIR.mkdir(parents=True, exist_ok=True)

    manifest = load_manifest()
    LabelHandler.manifest = manifest
    LabelHandler.image_list = sorted(manifest.keys())

    progress = load_progress()
    total = len(LabelHandler.image_list)
    labeled = len(progress["labeled"])
    skipped = len(progress["skipped"])

    print(f"=== CV Labeling Tool ===")
    print(f"Images dir:  {IMAGES_DIR}")
    print(f"Labels dir:  {LABELS_DIR}")
    print(f"Total images: {total}")
    print(f"Labeled:      {labeled}")
    print(f"Skipped:      {skipped}")
    print(f"Remaining:    {total - labeled - skipped}")
    print(f"")
    print(f"Open http://localhost:{PORT} in your browser")
    print(f"Press Ctrl+C to stop")
    print()

    server = http.server.HTTPServer(("127.0.0.1", PORT), LabelHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
        server.shutdown()


if __name__ == "__main__":
    main()
