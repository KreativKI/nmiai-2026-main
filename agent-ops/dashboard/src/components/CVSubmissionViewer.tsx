import { useState, useEffect } from "react";

interface ValidationFile {
  name: string;
  size_mb: number;
  ext: string;
}

interface ValidationStats {
  total_files: number;
  py_files: number;
  weight_files: number;
  total_size_mb: number;
  weight_size_mb: number;
}

interface ValidationResult {
  path: string;
  valid: boolean;
  errors: string[];
  warnings: string[];
  files: ValidationFile[];
  stats: ValidationStats;
}

const LIMITS = {
  total_size_mb: 420,
  weight_size_mb: 420,
  py_files: 10,
  weight_files: 3,
  total_files: 1000,
};

function ProgressBar({ value, max, label, color }: { value: number; max: number; label: string; color: string }) {
  const pct = Math.min((value / max) * 100, 100);
  const overLimit = value > max;
  return (
    <div className="flex items-center gap-2 text-xs">
      <span className="w-20 text-sky-600 text-right">{label}</span>
      <div className="flex-1 h-3 bg-white/30 rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full transition-all ${overLimit ? "bg-red-500" : color}`}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className={`w-24 text-right font-mono ${overLimit ? "text-red-600 font-bold" : "text-sky-700"}`}>
        {typeof value === "number" && value % 1 !== 0 ? value.toFixed(1) : value} / {max}
      </span>
    </div>
  );
}

export function CVSubmissionViewer() {
  const [result, setResult] = useState<ValidationResult | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    fetch("/data/cv_validation.json")
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then((d) => { setResult(d as ValidationResult); setLoading(false); })
      .catch(() => { setResult(null); setLoading(false); });
  }, []);

  if (loading) {
    return null;
  }

  if (!result) {
    return (
      <div className="rounded-2xl bg-white/50 backdrop-blur-sm border border-white/30 p-4">
        <h3 className="text-sm font-bold text-sky-700 font-[Fredoka] mb-2">
          ZIP Submission Validator
        </h3>
        <p className="text-xs text-sky-400">
          No validation data yet. Run before uploading:
        </p>
        <code className="text-[10px] bg-white/60 px-2 py-1 rounded block mt-2 text-sky-600">
          ./tools/validate_cv_zip_to_json.sh /path/to/submission.zip
        </code>
      </div>
    );
  }

  const s = result.stats;

  return (
    <div className="rounded-2xl bg-white/50 backdrop-blur-sm border border-white/30 p-4 space-y-3">
      {/* Header with PASS/FAIL badge */}
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-bold text-sky-700 font-[Fredoka]">
          ZIP Validation
        </h3>
        <span className={`px-3 py-1 rounded-full text-xs font-bold ${
          result.valid
            ? "bg-green-100 text-green-800 border border-green-300"
            : "bg-red-100 text-red-800 border border-red-300"
        }`}>
          {result.valid ? "PASS" : "FAIL"}
        </span>
      </div>

      {/* File path */}
      <p className="text-[10px] text-sky-400 font-mono truncate">{result.path}</p>

      {/* Size bars */}
      <div className="space-y-1.5">
        <ProgressBar value={s.total_size_mb} max={LIMITS.total_size_mb} label="Total size" color="bg-sky-500" />
        <ProgressBar value={s.weight_size_mb} max={LIMITS.weight_size_mb} label="Weights" color="bg-purple-500" />
        <ProgressBar value={s.py_files} max={LIMITS.py_files} label=".py files" color="bg-amber-500" />
        <ProgressBar value={s.weight_files} max={LIMITS.weight_files} label="Weight files" color="bg-blue-500" />
      </div>

      {/* Errors */}
      {result.errors.length > 0 && (
        <div className="bg-red-50/80 border border-red-200 rounded-lg p-3">
          <p className="text-xs font-bold text-red-700 mb-1">
            Errors ({result.errors.length})
          </p>
          <div className="space-y-1 max-h-[150px] overflow-y-auto">
            {result.errors.map((e, i) => (
              <p key={i} className="text-[11px] text-red-600 font-mono">{e}</p>
            ))}
          </div>
        </div>
      )}

      {/* Warnings */}
      {result.warnings.length > 0 && (
        <div className="bg-amber-50/80 border border-amber-200 rounded-lg p-3">
          <p className="text-xs font-bold text-amber-700 mb-1">
            Warnings ({result.warnings.length})
          </p>
          {result.warnings.map((w, i) => (
            <p key={i} className="text-[11px] text-amber-600">{w}</p>
          ))}
        </div>
      )}

      {/* File list */}
      <details className="text-xs">
        <summary className="cursor-pointer text-sky-600 font-semibold">
          Files in ZIP ({result.files.length})
        </summary>
        <div className="mt-2 max-h-[200px] overflow-y-auto space-y-0.5">
          {result.files.map((f, i) => (
            <div key={i} className="flex justify-between font-mono text-[10px]">
              <span className={`truncate ${
                f.name === "run.py" ? "text-green-700 font-bold" :
                f.ext === ".py" ? "text-sky-700" :
                f.ext && [".pt", ".pth", ".onnx", ".safetensors", ".npy"].includes(f.ext) ? "text-purple-700" :
                "text-sky-500"
              }`}>
                {f.name}
              </span>
              <span className="text-sky-400 ml-2 flex-shrink-0">{f.size_mb} MB</span>
            </div>
          ))}
        </div>
      </details>

      {/* Refresh hint */}
      <p className="text-[10px] text-sky-300">
        Re-run: <code className="bg-white/60 px-1 rounded">./tools/validate_cv_zip_to_json.sh path/to/zip</code>
      </p>
    </div>
  );
}
