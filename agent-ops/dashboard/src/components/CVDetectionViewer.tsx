import { useState, useEffect, useRef, useCallback } from "react";

interface Detection {
  image_id: number;
  category_id: number;
  bbox: [number, number, number, number]; // [x, y, w, h] COCO format
  score: number;
}

interface CategoryInfo {
  id: number;
  name: string;
}

export function CVDetectionViewer() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const imgRef = useRef<HTMLImageElement | null>(null);
  const [detections, setDetections] = useState<Detection[]>([]);
  const [categories, setCategories] = useState<CategoryInfo[]>([]);
  const [imageUrl, setImageUrl] = useState<string | null>(null);
  const [selectedImageId, setSelectedImageId] = useState<number | null>(null);
  const [threshold, setThreshold] = useState(0.3);
  const [error, setError] = useState<string | null>(null);

  // Load predictions
  useEffect(() => {
    fetch("/data/cv_predictions.json")
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then((d) => {
        setDetections(d as Detection[]);
        // Find unique image IDs
        const ids = [...new Set((d as Detection[]).map((det) => det.image_id))];
        if (ids[0] !== undefined) setSelectedImageId(ids[0]);
      })
      .catch((e) => setError(String(e)));
  }, []);

  // Load categories
  useEffect(() => {
    fetch("/data/cv_categories.json")
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then((d) => setCategories(d as CategoryInfo[]))
      .catch(() => {
        // Categories are optional
      });
  }, []);

  // Load image when selected
  useEffect(() => {
    if (selectedImageId === null) return;
    const paddedId = String(selectedImageId).padStart(5, "0");
    const url = `/data/cv_images/img_${paddedId}.jpg`;
    setImageUrl(url);
  }, [selectedImageId]);

  const drawDetections = useCallback(() => {
    const canvas = canvasRef.current;
    const img = imgRef.current;
    if (!canvas || !img || !img.complete) return;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    canvas.width = img.naturalWidth;
    canvas.height = img.naturalHeight;

    ctx.drawImage(img, 0, 0);

    // Filter detections for this image and threshold
    const filtered = detections.filter(
      (d) => d.image_id === selectedImageId && d.score >= threshold,
    );

    const catMap = new Map(categories.map((c) => [c.id, c.name]));

    for (const det of filtered) {
      const [x, y, w, h] = det.bbox;
      const alpha = 0.3 + det.score * 0.7;

      // Color by confidence
      const hue = det.score * 120; // 0=red, 60=yellow, 120=green
      ctx.strokeStyle = `hsla(${hue}, 80%, 50%, ${alpha})`;
      ctx.lineWidth = 2;
      ctx.strokeRect(x, y, w, h);

      // Label
      const catName = catMap.get(det.category_id);
      const label = catName
        ? `${catName.slice(0, 20)} ${(det.score * 100).toFixed(0)}%`
        : `cat${det.category_id} ${(det.score * 100).toFixed(0)}%`;

      ctx.font = "12px monospace";
      const textWidth = ctx.measureText(label).width;
      ctx.fillStyle = `hsla(${hue}, 80%, 50%, 0.8)`;
      ctx.fillRect(x, y - 16, textWidth + 6, 16);
      ctx.fillStyle = "white";
      ctx.fillText(label, x + 3, y - 4);
    }
  }, [detections, categories, selectedImageId, threshold]);

  // Redraw on image load
  const handleImageLoad = useCallback(() => {
    drawDetections();
  }, [drawDetections]);

  useEffect(() => {
    drawDetections();
  }, [drawDetections]);

  const imageIds = [...new Set(detections.map((d) => d.image_id))].sort((a, b) => a - b);
  const filteredCount = detections.filter(
    (d) => d.image_id === selectedImageId && d.score >= threshold,
  ).length;

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-bold text-sky-700 font-[Fredoka]">
          Detection Results
        </h3>
        <span className="text-[10px] text-sky-400">
          {filteredCount} detections above {(threshold * 100).toFixed(0)}%
        </span>
      </div>

      {error ? (
        <div className="rounded-2xl bg-white/50 backdrop-blur-sm border border-white/30 p-4">
          <p className="text-xs text-sky-400">
            No prediction data yet. Place files in public/data/:
          </p>
          <ul className="text-[10px] text-sky-300 mt-1 list-disc list-inside">
            <li>cv_predictions.json (COCO format predictions array)</li>
            <li>cv_categories.json (category ID to name mapping)</li>
            <li>cv_images/ folder with shelf images</li>
          </ul>
        </div>
      ) : (
        <>
          {/* Controls */}
          <div className="flex gap-3 items-center">
            {/* Image selector */}
            {imageIds.length > 0 && (
              <select
                value={selectedImageId ?? ""}
                onChange={(e) => setSelectedImageId(Number(e.target.value))}
                className="px-3 py-1.5 rounded-lg bg-white/60 border border-white/40 text-xs text-sky-700"
              >
                {imageIds.map((id) => (
                  <option key={id} value={id}>
                    img_{String(id).padStart(5, "0")}.jpg
                  </option>
                ))}
              </select>
            )}

            {/* Confidence threshold */}
            <div className="flex items-center gap-2">
              <span className="text-xs text-sky-600">Min confidence:</span>
              <input
                type="range"
                min="0"
                max="1"
                step="0.05"
                value={threshold}
                onChange={(e) => setThreshold(Number(e.target.value))}
                className="w-24 accent-sky-600"
              />
              <span className="text-xs text-sky-700 font-semibold w-8">
                {(threshold * 100).toFixed(0)}%
              </span>
            </div>
          </div>

          {/* Canvas */}
          <div className="rounded-2xl bg-slate-800/60 backdrop-blur-sm border border-white/20 overflow-auto max-h-[500px]">
            {imageUrl && (
              <img
                ref={(el) => { imgRef.current = el; }}
                src={imageUrl}
                onLoad={handleImageLoad}
                onError={() => setError(`Failed to load ${imageUrl}`)}
                className="hidden"
                alt=""
              />
            )}
            <canvas
              ref={canvasRef}
              className="max-w-full"
            />
            {!imageUrl && (
              <div className="flex items-center justify-center h-[300px] text-sky-400 text-sm">
                Select an image to view detections
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}
