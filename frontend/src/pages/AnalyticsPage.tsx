import { useMemo } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { ChartColumn, LoaderCircle } from "lucide-react";
import EmptyState from "../components/common/EmptyState";
import Notice from "../components/common/Notice";
import PageShell from "../components/common/PageShell";
import ChartCard from "../components/dashboard/ChartCard";
import { AXIS_TICK, BAR_CURSOR, TOOLTIP_PROPS } from "../components/dashboard/chartStyle";
import SampleDataNote from "../components/dashboard/SampleDataNote";
import StatCard from "../components/dashboard/StatCard";
import { useHistory } from "../hooks/useHistory";
import {
  getLanguageTotals,
  getProjectScores,
  getScoreTrend,
  getSeverityTotals,
  getSummary,
} from "../utils/analytics";
import type { AnalysisRecord } from "../types";

function Charts({ records }: { records: AnalysisRecord[] }) {
  const summary = useMemo(() => getSummary(records), [records]);
  const trend = useMemo(() => getScoreTrend(records), [records]);
  const severity = useMemo(() => getSeverityTotals(records), [records]);
  const languages = useMemo(() => getLanguageTotals(records), [records]);
  const projects = useMemo(() => getProjectScores(records), [records]);

  if (summary.analyses === 0) {
    return (
      <div className="glass-panel rounded-xl border py-12">
        <EmptyState icon={<ChartColumn size={32} />} title="No finished analyses yet">
          Charts appear after your first completed analysis.
        </EmptyState>
      </div>
    );
  }

  return (
    <>
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <StatCard label="Projects analysed" value={summary.projects} />
        <StatCard label="Files analysed" value={summary.files} />
        <StatCard
          label="Average quality score"
          value={summary.avgScore === null ? "—" : summary.avgScore}
          hint="out of 100"
        />
        <StatCard label="Issues found" value={summary.issues} />
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <ChartCard
          title="Quality score trend"
          subtitle="Average score per month"
          className="lg:col-span-2"
        >
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={trend} margin={{ top: 8, right: 16, left: -16, bottom: 0 }}>
                <CartesianGrid stroke="var(--line)" strokeDasharray="3 3" vertical={false} />
                <XAxis dataKey="month" tick={AXIS_TICK} stroke="var(--line)" />
                <YAxis domain={[0, 100]} tick={AXIS_TICK} stroke="var(--line)" />
                <Tooltip {...TOOLTIP_PROPS} />
                <Line
                  type="monotone"
                  dataKey="score"
                  name="Average score"
                  stroke="var(--saffron)"
                  strokeWidth={2.5}
                  dot={{ r: 4, fill: "var(--saffron)", stroke: "var(--bg-panel)" }}
                  activeDot={{ r: 6 }}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </ChartCard>

        <ChartCard title="Issue severity" subtitle="All finished analyses">
          <div className="relative h-56">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={severity}
                  dataKey="value"
                  nameKey="name"
                  innerRadius="60%"
                  outerRadius="90%"
                  paddingAngle={2}
                  stroke="var(--bg-panel)"
                />
                <Tooltip {...TOOLTIP_PROPS} />
              </PieChart>
            </ResponsiveContainer>
            <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
              <span className="font-mono text-2xl font-semibold">{summary.issues}</span>
              <span className="text-xs text-muted">issues</span>
            </div>
          </div>

          <ul className="mt-4 grid grid-cols-2 gap-x-4 gap-y-1.5 text-sm">
            {severity.map((item) => (
              <li key={item.name} className="flex items-center gap-2">
                <span
                  className="h-2.5 w-2.5 shrink-0 rounded-full"
                  style={{ background: item.fill }}
                />
                <span className="text-muted">{item.name}</span>
                <span className="ml-auto font-mono">{item.value}</span>
              </li>
            ))}
          </ul>
        </ChartCard>

        <ChartCard title="Languages" subtitle="Analyses per language">
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={languages} margin={{ top: 8, right: 16, left: -16, bottom: 0 }}>
                <CartesianGrid stroke="var(--line)" strokeDasharray="3 3" vertical={false} />
                <XAxis dataKey="name" tick={AXIS_TICK} stroke="var(--line)" />
                <YAxis allowDecimals={false} tick={AXIS_TICK} stroke="var(--line)" />
                <Tooltip {...TOOLTIP_PROPS} cursor={BAR_CURSOR} />
                <Bar
                  dataKey="analyses"
                  name="Analyses"
                  fill="var(--saffron)"
                  radius={[4, 4, 0, 0]}
                />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </ChartCard>

        <ChartCard
          title="Project comparison"
          subtitle="Average quality score per project"
          className="lg:col-span-2"
        >
          <div style={{ height: projects.length * 44 + 40 }}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart
                data={projects}
                layout="vertical"
                margin={{ top: 4, right: 16, left: 8, bottom: 0 }}
              >
                <CartesianGrid stroke="var(--line)" strokeDasharray="3 3" horizontal={false} />
                <XAxis
                  type="number"
                  domain={[0, 100]}
                  tick={AXIS_TICK}
                  stroke="var(--line)"
                />
                <YAxis
                  type="category"
                  dataKey="name"
                  width={110}
                  tick={AXIS_TICK}
                  stroke="var(--line)"
                />
                <Tooltip {...TOOLTIP_PROPS} cursor={BAR_CURSOR} />
                <Bar
                  dataKey="score"
                  name="Average score"
                  fill="var(--saffron)"
                  radius={[0, 4, 4, 0]}
                />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </ChartCard>
      </div>
    </>
  );
}

export default function AnalyticsPage() {
  const { records, loading, error } = useHistory();

  return (
    <PageShell title="Analytics">
      <div className="space-y-4">
        <SampleDataNote />

        {loading && (
          <p className="flex items-center gap-2 text-sm text-muted">
            <LoaderCircle size={16} className="animate-spin" />
            Loading
          </p>
        )}

        {error && <Notice kind="error">{error}</Notice>}

        {records && <Charts records={records} />}
      </div>
    </PageShell>
  );
}