interface MetricCardProps {
  label: string;
  value: string | number;
  subtitle?: string;
  color?: string;
}

export function MetricCard({ label, value, subtitle, color }: MetricCardProps) {
  return (
    <div className="rounded-2xl bg-white/70 backdrop-blur-sm border border-white/40 shadow-lg px-5 py-4 min-w-[140px]">
      <p className="text-xs font-medium text-sky-600 uppercase tracking-wide">
        {label}
      </p>
      <p className={`text-2xl font-bold font-[Fredoka] ${color ?? "text-sky-900"}`}>
        {value}
      </p>
      {subtitle && (
        <p className="text-xs text-sky-500 mt-0.5">{subtitle}</p>
      )}
    </div>
  );
}
