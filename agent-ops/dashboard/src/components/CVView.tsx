import { useState, useEffect } from "react";
import { MetricCard } from "./MetricCard";
import { CVDetectionViewer } from "./CVDetectionViewer";
import { CVSubmissionViewer } from "./CVSubmissionViewer";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  ResponsiveContainer,
  Tooltip,
  Legend,
} from "recharts";

interface TrainingLog {
  epoch: number;
  model?: string;
  mAP50: number;
  mAP5095: number;
  precision: number;
  recall: number;
}

const CHART_TOOLTIP_STYLE: React.CSSProperties = {
  backgroundColor: "rgba(255,255,255,0.95)",
  border: "1px solid rgba(14,165,233,0.2)",
  borderRadius: "12px",
  fontSize: "12px",
  padding: "8px 12px",
};

export function CVView() {
  const [allLogs, setAllLogs] = useState<TrainingLog[]>([]);
  const [selectedModel, setSelectedModel] = useState<string>("yolo11m");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch("/data/cv_training_log.json")
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then((d) => {
        const data = d as TrainingLog[];
        setAllLogs(data);
        // Auto-select model with most epochs
        const models = [...new Set(data.map((e) => e.model ?? "unknown"))];
        if (models.length > 0) {
          const best = models.reduce((a, b) =>
            data.filter((e) => e.model === a).length >= data.filter((e) => e.model === b).length ? a : b
          );
          setSelectedModel(best);
        }
      })
      .catch((e) => setError(String(e)));
  }, []);

  const models = [...new Set(allLogs.map((e) => e.model ?? "unknown"))];
  const logs = allLogs.filter((e) => (e.model ?? "unknown") === selectedModel);
  const latest = logs.length > 0 ? logs[logs.length - 1] : null;
  const bestMAP50 = logs.length > 0 ? Math.max(...logs.map((e) => e.mAP50)) : 0;
  const bestMAP5095 = logs.length > 0 ? Math.max(...logs.map((e) => e.mAP5095)) : 0;

  return (
    <div className="flex-1 flex flex-col overflow-auto p-6 gap-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold text-sky-800 font-[Fredoka]">
            NorgesGruppen - Object Detection
          </h2>
          <p className="text-xs text-sky-500">
            357 categories, 70% detection mAP + 30% classification mAP
          </p>
        </div>
        {/* Model selector */}
        {models.length > 1 && (
          <div className="flex gap-2">
            {models.map((m) => (
              <button
                key={m}
                onClick={() => setSelectedModel(m)}
                className={`px-3 py-1.5 rounded-full text-xs font-semibold transition-all ${
                  selectedModel === m
                    ? "bg-sky-800 text-white shadow-md"
                    : "bg-white/60 text-sky-700 hover:bg-white/80"
                }`}
              >
                {m} ({allLogs.filter((e) => e.model === m).length} ep)
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Metrics */}
      <div className="flex gap-3 flex-wrap">
        <MetricCard
          label="Best mAP50"
          value={bestMAP50 > 0 ? bestMAP50.toFixed(3) : "-"}
          subtitle={selectedModel}
          color={bestMAP50 > 0.5 ? "text-green-700" : "text-sky-900"}
        />
        <MetricCard
          label="Best mAP50-95"
          value={bestMAP5095 > 0 ? bestMAP5095.toFixed(3) : "-"}
          subtitle="primary metric"
        />
        <MetricCard
          label="Latest mAP50"
          value={latest ? latest.mAP50.toFixed(3) : "-"}
          subtitle={latest ? `epoch ${latest.epoch}` : "no data"}
        />
        <MetricCard
          label="mAP50-95"
          value={latest ? latest.mAP5095.toFixed(3) : "-"}
          subtitle="primary metric"
        />
        <MetricCard
          label="Precision"
          value={latest ? latest.precision.toFixed(3) : "-"}
        />
        <MetricCard
          label="Recall"
          value={latest ? latest.recall.toFixed(3) : "-"}
        />
        <MetricCard label="Epochs" value={logs.length} subtitle="trained" />
        <MetricCard label="Submissions" value="10/day" subtitle="resets 01:00 CET" />
      </div>

      {/* Training curves */}
      <div className="rounded-2xl bg-white/50 backdrop-blur-sm border border-white/30 p-4 flex-1 min-h-[300px]">
        <h3 className="text-sm font-bold text-sky-700 font-[Fredoka] mb-3">
          Training Curves
        </h3>

        {error && (
          <div className="text-sm text-amber-600 mb-2">
            No training log found. Place cv_training_log.json in public/data/
            <br />
            <span className="text-xs text-amber-400">
              Pull from GCP: gcloud compute scp cv-train-1:~/training/results.json public/data/cv_training_log.json --zone=europe-west1-c
            </span>
          </div>
        )}

        {logs.length > 0 ? (
          <ResponsiveContainer width="100%" height={280}>
            <LineChart data={logs} margin={{ top: 4, right: 8, bottom: 0, left: 0 }}>
              <XAxis
                dataKey="epoch"
                tick={{ fontSize: 10, fill: "#7dd3fc" }}
                tickLine={false}
                axisLine={false}
              />
              <YAxis
                domain={[0, 1]}
                tick={{ fontSize: 10, fill: "#7dd3fc" }}
                tickLine={false}
                axisLine={false}
                width={40}
              />
              <Tooltip contentStyle={CHART_TOOLTIP_STYLE} />
              <Legend wrapperStyle={{ fontSize: 11 }} />
              <Line
                type="monotone"
                dataKey="mAP50"
                stroke="#0284c7"
                strokeWidth={2}
                dot={false}
                name="mAP50"
              />
              <Line
                type="monotone"
                dataKey="mAP5095"
                stroke="#059669"
                strokeWidth={2}
                dot={false}
                name="mAP50-95"
              />
              <Line
                type="monotone"
                dataKey="precision"
                stroke="#f59e0b"
                strokeWidth={1.5}
                dot={false}
                name="Precision"
                strokeDasharray="4 2"
              />
              <Line
                type="monotone"
                dataKey="recall"
                stroke="#ef4444"
                strokeWidth={1.5}
                dot={false}
                name="Recall"
                strokeDasharray="4 2"
              />
            </LineChart>
          </ResponsiveContainer>
        ) : !error ? (
          <div className="flex items-center justify-center h-[200px] text-sky-400">
            Loading training data...
          </div>
        ) : null}
      </div>

      {/* Detection viewer */}
      {/* ZIP Submission Validator */}
      <CVSubmissionViewer />

      {/* Detection viewer */}
      <CVDetectionViewer />

      {/* Submission info */}
      <div className="rounded-2xl bg-white/30 backdrop-blur-sm border border-white/20 p-3">
        <p className="text-xs text-sky-500">
          GCP VM: <span className="font-mono">cv-train-1</span> (europe-west1-c) |
          Sandbox: Python 3.11, L4 GPU, no network |
          Max: 420 MB weights, 3 weight files, 10 .py files
        </p>
      </div>
    </div>
  );
}
