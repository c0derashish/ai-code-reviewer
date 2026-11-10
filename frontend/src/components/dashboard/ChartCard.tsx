import type { ReactNode } from "react";

type ChartCardProps = {
  title: string;
  subtitle?: string;
  className?: string;
  children: ReactNode;
};

export default function ChartCard({ title, subtitle, className = "", children }: ChartCardProps) {
  return (
    <section className={`glass-panel rounded-xl border p-4 sm:p-5 ${className}`}>
      <h2 className="font-medium">{title}</h2>
      {subtitle && <p className="text-xs text-muted">{subtitle}</p>}
      <div className="mt-4">{children}</div>
    </section>
  );
}