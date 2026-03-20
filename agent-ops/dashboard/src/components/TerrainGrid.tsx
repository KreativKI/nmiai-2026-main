import { useRef, useEffect, useCallback, useState } from "react";
import { useUIStore } from "../stores/uiStore";
import { TERRAIN_NAMES } from "../types/dashboard";
import {
  renderTerrainGrid,
  centerCamera,
  fitScale,
  pixelToGrid,
  type Camera,
} from "../canvas/TerrainRenderer";

interface TerrainGridProps {
  grid: number[][];
  groundTruth?: number[][] | null;
  label?: string;
  isDiffMode?: boolean;
}

export function TerrainGrid({ grid, groundTruth, label, isDiffMode }: TerrainGridProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const cameraRef = useRef<Camera>({ offsetX: 0, offsetY: 0, scale: 1 });
  const isDragging = useRef(false);
  const lastMouse = useRef({ x: 0, y: 0 });
  const startMouse = useRef({ x: 0, y: 0 });
  const rafId = useRef<number>(0);
  const dprRef = useRef(window.devicePixelRatio || 1);
  const [tooltip, setTooltip] = useState<string | null>(null);
  const isFullscreen = useUIStore((s) => s.isCanvasFullscreen);
  const toggleFullscreen = useUIStore((s) => s.toggleCanvasFullscreen);
  const showGT = useUIStore((s) => s.showGroundTruth);

  const height = grid.length;
  const width = grid[0]?.length ?? 0;

  const fitAndCenter = useCallback(
    (w: number, h: number) => {
      const scale = fitScale(width, height, w, h);
      cameraRef.current = centerCamera(width, height, w, h, scale);
    },
    [width, height],
  );

  const draw = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    dprRef.current = window.devicePixelRatio || 1;
    const dpr = dprRef.current;
    const cssW = canvas.width / dpr;
    const cssH = canvas.height / dpr;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    renderTerrainGrid(
      ctx,
      grid,
      cameraRef.current,
      cssW,
      cssH,
      showGT ? groundTruth : null,
      isDiffMode,
    );
  }, [grid, groundTruth, showGT, isDiffMode]);

  // Resize observer
  useEffect(() => {
    const container = containerRef.current;
    const canvas = canvasRef.current;
    if (!container || !canvas) return;

    const observer = new ResizeObserver((entries) => {
      const entry = entries[0];
      if (!entry) return;
      const { width: w, height: h } = entry.contentRect;
      const dpr = window.devicePixelRatio || 1;
      dprRef.current = dpr;
      canvas.width = w * dpr;
      canvas.height = h * dpr;
      canvas.style.width = `${w}px`;
      canvas.style.height = `${h}px`;
      fitAndCenter(w, h);
      draw();
    });

    observer.observe(container);
    return () => observer.disconnect();
  }, [fitAndCenter, draw]);

  useEffect(() => { draw(); }, [draw]);

  // Pan
  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    isDragging.current = true;
    lastMouse.current = { x: e.clientX, y: e.clientY };
    startMouse.current = { x: e.clientX, y: e.clientY };
  }, []);

  const handleMouseMove = useCallback(
    (e: React.MouseEvent) => {
      if (!isDragging.current) return;
      const dx = e.clientX - lastMouse.current.x;
      const dy = e.clientY - lastMouse.current.y;
      lastMouse.current = { x: e.clientX, y: e.clientY };
      cameraRef.current = {
        ...cameraRef.current,
        offsetX: cameraRef.current.offsetX + dx,
        offsetY: cameraRef.current.offsetY + dy,
      };
      cancelAnimationFrame(rafId.current);
      rafId.current = requestAnimationFrame(draw);
    },
    [draw],
  );

  const handleMouseUp = useCallback((e: React.MouseEvent) => {
    const dx = e.clientX - startMouse.current.x;
    const dy = e.clientY - startMouse.current.y;
    const dist = Math.sqrt(dx * dx + dy * dy);

    if (dist < 3 && canvasRef.current) {
      const rect = canvasRef.current.getBoundingClientRect();
      const px = e.clientX - rect.left;
      const py = e.clientY - rect.top;
      const [gx, gy] = pixelToGrid(px, py, cameraRef.current);

      if (gx >= 0 && gy >= 0 && gx < width && gy < height) {
        const row = grid[gy];
        const terrain = row?.[gx];
        if (terrain !== undefined) {
          if (isDiffMode && terrain === -1) {
            setTooltip(`(${gx}, ${gy}) Unchanged`);
          } else if (isDiffMode) {
            const name = TERRAIN_NAMES[terrain] ?? `Unknown(${terrain})`;
            setTooltip(`(${gx}, ${gy}) Changed to ${name}`);
          } else {
            const name = TERRAIN_NAMES[terrain] ?? `Unknown(${terrain})`;
            setTooltip(`(${gx}, ${gy}) ${name}`);
          }
          setTimeout(() => setTooltip(null), 2000);
        }
      }
    }
    isDragging.current = false;
  }, [grid, width, height]);

  const handleMouseLeave = useCallback(() => {
    isDragging.current = false;
  }, []);

  // Zoom
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const onWheel = (e: WheelEvent) => {
      e.preventDefault();
      const rect = canvas.getBoundingClientRect();
      const mouseX = e.clientX - rect.left;
      const mouseY = e.clientY - rect.top;
      const zoomFactor = e.deltaY < 0 ? 1.1 : 0.9;
      const cam = cameraRef.current;
      const newScale = Math.max(0.5, Math.min(8, cam.scale * zoomFactor));
      const scaleRatio = newScale / cam.scale;
      cameraRef.current = {
        scale: newScale,
        offsetX: mouseX - (mouseX - cam.offsetX) * scaleRatio,
        offsetY: mouseY - (mouseY - cam.offsetY) * scaleRatio,
      };
      cancelAnimationFrame(rafId.current);
      rafId.current = requestAnimationFrame(draw);
    };

    canvas.addEventListener("wheel", onWheel, { passive: false });
    return () => {
      canvas.removeEventListener("wheel", onWheel);
      cancelAnimationFrame(rafId.current);
    };
  }, [draw]);

  // ESC exits fullscreen
  useEffect(() => {
    if (!isFullscreen) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") toggleFullscreen();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [isFullscreen, toggleFullscreen]);

  const handleReset = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const dpr = dprRef.current;
    fitAndCenter(canvas.width / dpr, canvas.height / dpr);
    draw();
  }, [fitAndCenter, draw]);

  return (
    <div
      ref={containerRef}
      className={
        isFullscreen
          ? "fixed inset-0 z-50 bg-slate-900/95"
          : "relative w-full h-full rounded-2xl overflow-hidden bg-slate-800/60 backdrop-blur-sm border border-white/20"
      }
    >
      <canvas
        ref={canvasRef}
        className="block cursor-grab active:cursor-grabbing"
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onMouseLeave={handleMouseLeave}
      />

      {/* Label */}
      {label && !isFullscreen && (
        <div className="absolute top-3 left-3 text-[10px] text-sky-300 font-mono bg-black/40 backdrop-blur-sm px-2 py-1 rounded-lg">
          {label} | {width}x{height}
        </div>
      )}

      {/* Tooltip */}
      {tooltip && (
        <div className="absolute top-3 right-3 px-3 py-1.5 rounded-full bg-sky-800 text-white text-xs font-semibold shadow-lg">
          {tooltip}
        </div>
      )}

      {/* Controls */}
      <div className={`absolute bottom-3 right-3 flex gap-2 ${isFullscreen ? "bottom-6 right-6" : ""}`}>
        <button
          onClick={toggleFullscreen}
          className="px-3 py-1.5 rounded-full bg-white/80 backdrop-blur-sm text-xs font-semibold text-sky-700 shadow-md hover:bg-white transition-colors border border-white/40"
        >
          {isFullscreen ? "Exit" : "Fullscreen"}
        </button>
        <button
          onClick={handleReset}
          className="px-3 py-1.5 rounded-full bg-white/80 backdrop-blur-sm text-xs font-semibold text-sky-700 shadow-md hover:bg-white transition-colors border border-white/40"
        >
          Reset
        </button>
      </div>
    </div>
  );
}
