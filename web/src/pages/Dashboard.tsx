import { useQuery } from "@tanstack/react-query";
import { ArrowRight, CalendarCheck, FileCheck2, GraduationCap, TrendingUp, UsersRound } from "lucide-react";
import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { Card, CardHeader, PageHeader, PageLoader } from "../components/ui";
import { useI18n } from "../i18n";
import { api } from "../lib/api";
import { useUser } from "../lib/auth";
import type { Stats } from "../lib/types";

function StatCard({ label, value, icon, to }: { label: string; value: number; icon: ReactNode; to?: string }) {
  const body = (
    <Card className="flex items-center gap-4 p-5 transition-shadow hover:shadow-md">
      <div className="flex size-11 shrink-0 items-center justify-center rounded-xl bg-brand-50 text-brand-700">{icon}</div>
      <div className="min-w-0">
        <p className="truncate text-[13px] font-medium text-slate-500">{label}</p>
        <p className="mt-0.5 text-2xl font-semibold tracking-tight text-slate-900 tabular">{value.toLocaleString()}</p>
      </div>
    </Card>
  );
  return to ? <Link to={to}>{body}</Link> : body;
}

function RegistrationsChart({ data }: { data: Stats["per_day"] }) {
  const { locale, t } = useI18n();
  const max = Math.max(1, ...data.map((d) => d.count));
  const total = data.reduce((s, d) => s + d.count, 0);
  if (total === 0) return <p className="py-16 text-center text-sm text-slate-400">{t("dashboard.no_data")}</p>;
  const label = (iso: string) => new Date(`${iso}T12:00:00`).toLocaleDateString(locale, { day: "numeric", month: "short" });
  return (
    <div>
      <div className="flex h-44 items-end gap-[3px]">
        {data.map((d) => (
          <div key={d.date} className="group relative flex h-full flex-1 flex-col justify-end">
            <div
              className="min-h-[2px] rounded-t-[3px] bg-brand-500/85 transition-colors group-hover:bg-brand-700"
              style={{ height: `${(d.count / max) * 100}%` }}
            />
            <div className="pointer-events-none absolute bottom-full left-1/2 z-10 mb-2 hidden -translate-x-1/2 rounded-md bg-slate-900 px-2 py-1 text-[11px] whitespace-nowrap text-white group-hover:block">
              {label(d.date)}: <b className="tabular">{d.count}</b>
            </div>
          </div>
        ))}
      </div>
      <div className="mt-2 flex justify-between text-[11px] text-slate-400 tabular">
        <span>{label(data[0].date)}</span>
        <span>{label(data[Math.floor(data.length / 2)].date)}</span>
        <span>{label(data[data.length - 1].date)}</span>
      </div>
    </div>
  );
}

function DocumentsBreakdown({ docs }: { docs: Stats["documents"] }) {
  const { t } = useI18n();
  const rows = [
    { key: "complete", label: t("dashboard.docs_complete"), value: docs.complete, color: "bg-emerald-500", filter: "complete" },
    { key: "no_photo", label: t("dashboard.docs_no_photo"), value: docs.no_photo, color: "bg-amber-400", filter: "missing" },
    { key: "no_cv", label: t("dashboard.docs_no_cv"), value: docs.no_cv, color: "bg-orange-400", filter: "missing" },
  ];
  const total = Math.max(1, docs.complete + Math.max(docs.no_photo, docs.no_cv));
  return (
    <div>
      <div className="flex h-2.5 overflow-hidden rounded-full bg-slate-100">
        <div className="bg-emerald-500" style={{ width: `${(docs.complete / total) * 100}%` }} />
      </div>
      <ul className="mt-5 space-y-1">
        {rows.map((r) => (
          <li key={r.key}>
            <Link
              to={`/students?docs=${r.filter}`}
              className="-mx-2 flex items-center justify-between rounded-md px-2 py-1.5 text-sm hover:bg-slate-50"
            >
              <span className="flex items-center gap-2.5 text-slate-600">
                <span className={`size-2.5 rounded-full ${r.color}`} />
                {r.label}
              </span>
              <span className="font-medium text-slate-900 tabular">{r.value}</span>
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}

export function DashboardPage() {
  const { t } = useI18n();
  const user = useUser();
  const { data, isLoading } = useQuery({ queryKey: ["stats"], queryFn: () => api.get<Stats>("/api/stats") });
  if (isLoading || !data) return <PageLoader />;

  const firstName = (user.name || user.username).split(/\s/)[0];
  const subtitle =
    user.is_admin || user.is_tutor
      ? t("dashboard.subtitle_all")
      : t("dashboard.subtitle_groups", { groups: user.leader_groups.map((g) => g.name).join(", ") });
  const maxGroup = Math.max(1, ...data.by_group.map((g) => g.students));
  const genderTotal = data.gender.male + data.gender.female || 1;

  return (
    <>
      <PageHeader title={t("dashboard.welcome", { name: firstName })} subtitle={subtitle} />

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard label={t("dashboard.students")} value={data.students} icon={<GraduationCap className="size-5" />} to="/students" />
        <StatCard label={t("dashboard.groups")} value={data.groups} icon={<UsersRound className="size-5" />} to="/groups" />
        <StatCard label={t("dashboard.today")} value={data.today} icon={<CalendarCheck className="size-5" />} />
        <StatCard label={t("dashboard.week")} value={data.last_7_days} icon={<TrendingUp className="size-5" />} />
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader title={t("dashboard.registrations")} />
          <div className="p-5">
            <RegistrationsChart data={data.per_day} />
          </div>
        </Card>
        <Card>
          <CardHeader title={t("dashboard.documents")} icon={<FileCheck2 className="size-[18px]" />} />
          <div className="p-5">
            <DocumentsBreakdown docs={data.documents} />
          </div>
        </Card>
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader
            title={t("dashboard.by_group")}
            actions={
              <Link to="/groups" className="inline-flex items-center gap-1 text-[13px] font-medium text-brand-700 hover:text-brand-800">
                {t("dashboard.view_all")} <ArrowRight className="size-3.5" />
              </Link>
            }
          />
          <ul className="max-h-[22rem] divide-y divide-slate-100 overflow-y-auto">
            {data.by_group.map((g) => (
              <li key={g.id}>
                <Link to={`/students?group_id=${g.id}`} className="flex items-center gap-4 px-5 py-2.5 hover:bg-slate-50">
                  <span className="w-24 shrink-0 text-sm font-medium text-slate-800">{g.name}</span>
                  <div className="h-2 flex-1 overflow-hidden rounded-full bg-slate-100">
                    <div className="h-full rounded-full bg-brand-500" style={{ width: `${(g.students / maxGroup) * 100}%` }} />
                  </div>
                  <span className="w-10 text-right text-sm text-slate-600 tabular">{g.students}</span>
                </Link>
              </li>
            ))}
          </ul>
        </Card>
        <Card>
          <CardHeader title={t("dashboard.gender")} />
          <div className="space-y-4 p-5">
            {(["male", "female"] as const).map((g) => (
              <div key={g}>
                <div className="mb-1.5 flex justify-between text-sm">
                  <span className="text-slate-600">{t(`gender.${g}`)}</span>
                  <span className="font-medium text-slate-900 tabular">
                    {data.gender[g]} <span className="font-normal text-slate-400">· {Math.round((data.gender[g] / genderTotal) * 100)}%</span>
                  </span>
                </div>
                <div className="h-2 overflow-hidden rounded-full bg-slate-100">
                  <div
                    className={g === "male" ? "h-full rounded-full bg-brand-500" : "h-full rounded-full bg-rose-400"}
                    style={{ width: `${(data.gender[g] / genderTotal) * 100}%` }}
                  />
                </div>
              </div>
            ))}
          </div>
        </Card>
      </div>
    </>
  );
}
