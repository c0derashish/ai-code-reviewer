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
import StatCard from "../components/dashboard/StatCard";
import { useAnalytics } from "../hooks/useAnalytics";
import type { AnalyticsData } from "../types/history";
import { SEVERITY_COLOR } from "../utils/analytics";
import { formatMonth } from "../utils/format";
import { getLanguageLabel } from "../utils/language";
import { SEVERITIES, SEVERITY_META } from "../utils/severity";

function Charts({ data }: { data: AnalyticsData }) {
  const trend = useMemo(
    () =>
      data.trend
        .filter((item) => item.issuesPer100Loc !== null)
        .map((item) => ({ month: formatMonth(item.month), value: item.issuesPer100Loc })),
    [data]
  );

  const severity = useMemo(
    () =>
      SEVERITIES.map((name) => ({
        name: SEVERITY_META[name].label,
        value: data.severity[name],
        fill: SEVERITY_COLOR[name],
      })).filter((item) => item.value > 0),
    [data]
  );

  const languages = useMemo(
    () => data.languages.map((item) => ({ name: getLanguageLabel(item.language), lines: item.lines })),
    [data]
  );

  const projects = useMemo(
    () =>
      data.projects
        .filter((item) => item.latestIssuesPer100Loc !== null)
        .map((item) => ({ name: item.projectName, value: item.latestIssuesPer100Loc }))
        .sort((a, b) => (a.value ?? 0) - (b.value ?? 0)),
    [data]
  );

  const totalIssues = severity.reduce((sum, item) => sum + item.value, 0);

  if (data.totals.analyses === 0) {
    return (
      <div className="glass-panel rounded-xl border py-12">
        <EmptyState icon={<ChartColumn size={32} />} title="No saved analyses yet">
          Charts appear after you analyse a project while signed in and "Saving" is on.
        </EmptyState>
      </div>
    );
  }

  return (
    <>
      <Notice kind="info">
        These charts use "issues per 100 code lines", counting only rule-based findings (the AI
        findings change from run to run). It is not a quality score, and a lower number does not
        prove better code or better skill. Totals, severity and languages use the latest analysis of
        each project.
      </Notice>

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <StatCard label="Projects" value={data.totals.projects} />
        <StatCard label="Files analysed" value={data.totals.filesAnalyzed} hint="latest of each project" />
        <StatCard label="Code lines" value={data.totals.loc} />
        <StatCard
          label="Issues per 100 lines"
          value={data.totals.issuesPer100Loc ?? "—"}
          hint={`${data.totals.issueCount} issues in total`}
        />
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <ChartCard
          title="Issues per 100 lines over time"
          subtitle="All analyses, grouped by month"
          className="lg:col-span-2"
        >
          {trend.length === 0 ? (
            <p className="text-sm text-muted">No analysis with code lines yet.</p>
          ) : (
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={trend} margin={{ top: 8, right: 16, left: -16, bottom: 0 }}>
                  <CartesianGrid stroke="var(--line)" strokeDasharray="3 3" vertical={false} />
                  <XAxis dataKey="month" tick={AXIS_TICK} stroke="var(--line)" />
                  <YAxis tick={AXIS_TICK} stroke="var(--line)" />
                  <Tooltip {...TOOLTIP_PROPS} />
                  <Line
                    type="monotone"
                    dataKey="value"
                    name="Issues per 100 lines"
                    stroke="var(--saffron)"
                    strokeWidth={2.5}
                    dot={{ r: 4, fill: "var(--saffron)", stroke: "var(--bg-panel)" }}
                    activeDot={{ r: 6 }}
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          )}
        </ChartCard>

        <ChartCard title="Issue severity" subtitle="Latest analysis of each project">
          {severity.length === 0 ? (
            <p className="text-sm text-muted">No issues found.</p>
          ) : (
            <>
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
                  <span className="font-mono text-2xl font-semibold">{totalIssues}</span>
                  <span className="text-xs text-muted">issues</span>
                </div>
              </div>

              <ul className="mt-4 grid grid-cols-2 gap-x-4 gap-y-1.5 text-sm">
                {severity.map((item) => (
                  <li key={item.name} className="flex items-center gap-2">
                    <span className="h-2.5 w-2.5 shrink-0 rounded-full" style={{ background: item.fill }} />
                    <span className="text-muted">{item.name}</span>
                    <span className="ml-auto font-mono">{item.value}</span>
                  </li>
                ))}
              </ul>
            </>
          )}
        </ChartCard>

        <ChartCard title="Languages" subtitle="Non-blank lines, latest analysis of each project">
          {languages.length === 0 ? (
            <p className="text-sm text-muted">No language data yet.</p>
          ) : (
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={languages} margin={{ top: 8, right: 16, left: -16, bottom: 0 }}>
                  <CartesianGrid stroke="var(--line)" strokeDasharray="3 3" vertical={false} />
                  <XAxis dataKey="name" tick={AXIS_TICK} stroke="var(--line)" />
                  <YAxis tick={AXIS_TICK} stroke="var(--line)" />
                  <Tooltip {...TOOLTIP_PROPS} cursor={BAR_CURSOR} />
                  <Bar dataKey="lines" name="Lines" fill="var(--saffron)" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}
        </ChartCard>

        <ChartCard
          title="Project comparison"
          subtitle="Issues per 100 lines in the latest analysis, lowest first"
          className="lg:col-span-2"
        >
          {projects.length === 0 ? (
            <p className="text-sm text-muted">No project has code lines yet.</p>
          ) : (
            <div style={{ height: projects.length * 44 + 40 }}>
              <ResponsiveContainer width="100%" height="100%">
                <BarChart
                  data={projects}
                  layout="vertical"
                  margin={{ top: 4, right: 16, left: 8, bottom: 0 }}
                >
                  <CartesianGrid stroke="var(--line)" strokeDasharray="3 3" horizontal={false} />
                  <XAxis type="number" tick={AXIS_TICK} stroke="var(--line)" />
                  <YAxis type="category" dataKey="name" width={130} tick={AXIS_TICK} stroke="var(--line)" />
                  <Tooltip {...TOOLTIP_PROPS} cursor={BAR_CURSOR} />
                  <Bar
                    dataKey="value"
                    name="Issues per 100 lines"
                    fill="var(--saffron)"
                    radius={[0, 4, 4, 0]}
                  />
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}
        </ChartCard>
      </div>

      {data.truncated && (
        <p className="text-xs text-muted">Only the 1000 newest analyses are used.</p>
      )}
    </>
  );
}

export default function AnalyticsPage() {
  const { data, loading, error } = useAnalytics();

  return (
    <PageShell title="Analytics">
      <div className="space-y-4">
        {loading && (
          <p className="flex items-center gap-2 text-sm text-muted">
            <LoaderCircle size={16} className="animate-spin" />
            Loading
          </p>
        )}

        {error && <Notice kind="error">{error}</Notice>}

        {data && <Charts data={data} />}
      </div>
    </PageShell>
  );
}