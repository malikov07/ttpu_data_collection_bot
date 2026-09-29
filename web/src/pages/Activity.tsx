import { keepPreviousData, useQuery } from "@tanstack/react-query";
import clsx from "clsx";
import {
  Activity as ActivityIcon,
  Download,
  Eye,
  FileText,
  LogIn,
  Search,
  Settings,
  ShieldCheck,
  UserPen,
  UsersRound,
  type LucideIcon,
} from "lucide-react";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Card, EmptyState, Input, PageHeader, Pagination, Select, Spinner } from "../components/ui";
import { useI18n, type MessageKey } from "../i18n";
import { api } from "../lib/api";
import { actorLabel, formatDateTime } from "../lib/format";
import type { AuditEntry, Page } from "../lib/types";

const FILTERS: { value: string; label: MessageKey }[] = [
  { value: "", label: "activity.all" },
  { value: "auth", label: "activity.f_auth" },
  { value: "student.", label: "activity.f_student" },
  { value: "document", label: "activity.f_document" },
  { value: "group", label: "activity.f_group" },
  { value: "account", label: "activity.f_account" },
  { value: "settings", label: "activity.f_settings" },
  { value: "students.export", label: "activity.f_export" },
];

function iconFor(action: string): { icon: LucideIcon; tone: string } {
  if (action.endsWith("login_failed")) return { icon: LogIn, tone: "bg-red-50 text-red-600" };
  if (action.startsWith("auth")) return { icon: LogIn, tone: "bg-slate-100 text-slate-600" };
  if (action === "document.view") return { icon: Eye, tone: "bg-sky-50 text-sky-600" };
  if (action.startsWith("document")) return { icon: FileText, tone: "bg-brand-50 text-brand-700" };
  if (action.startsWith("students.export")) return { icon: Download, tone: "bg-emerald-50 text-emerald-600" };
  if (action.startsWith("student")) return { icon: UserPen, tone: "bg-brand-50 text-brand-700" };
  if (action.startsWith("group")) return { icon: UsersRound, tone: "bg-violet-50 text-violet-600" };
  if (action.startsWith("account")) return { icon: ShieldCheck, tone: "bg-amber-50 text-amber-700" };
  return { icon: Settings, tone: "bg-slate-100 text-slate-600" };
}

function describeDetails(entry: AuditEntry): string | null {
  if (!entry.details) return null;
  return Object.entries(entry.details)
    .map(([k, v]) => (Array.isArray(v) && v.length === 2 ? `${k}: ${String(v[0] ?? "—")} → ${String(v[1] ?? "—")}` : `${k}: ${String(v)}`))
    .join(" · ");
}

export function ActivityPage() {
  const { t, locale } = useI18n();
  const [action, setAction] = useState("");
  const [search, setSearch] = useState("");
  const [q, setQ] = useState("");
  const [page, setPage] = useState(1);
  useEffect(() => {
    const id = setTimeout(() => {
      setQ(search);
      setPage(1);
    }, 300);
    return () => clearTimeout(id);
  }, [search]);

  const { data, isLoading, isFetching } = useQuery({
    queryKey: ["audit", { action, q, page }],
    queryFn: () => api.get<Page<AuditEntry>>("/api/audit", { action, q, page, page_size: 50 }),
    placeholderData: keepPreviousData,
  });

  return (
    <>
      <PageHeader title={t("activity.title")} subtitle={t("activity.subtitle")} />
      <Card>
        <div className="flex flex-col gap-3 border-b border-slate-100 p-4 sm:flex-row">
          <div className="relative flex-1">
            <Search className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-slate-400" />
            <Input value={search} onChange={(e) => setSearch(e.target.value)} placeholder={t("activity.search")} className="pl-9" />
          </div>
          <Select
            value={action}
            onChange={(e) => {
              setAction(e.target.value);
              setPage(1);
            }}
            className="sm:w-56"
          >
            {FILTERS.map((f) => (
              <option key={f.value} value={f.value}>
                {t(f.label)}
              </option>
            ))}
          </Select>
        </div>

        {isLoading ? (
          <div className="flex h-64 items-center justify-center">
            <Spinner />
          </div>
        ) : !data?.items.length ? (
          <EmptyState icon={<ActivityIcon className="size-6" />} title={t("activity.empty")} />
        ) : (
          <ul className={clsx("divide-y divide-slate-100 transition-opacity", isFetching && "opacity-60")}>
            {data.items.map((e) => {
              const { icon: Icon, tone } = iconFor(e.action);
              const label = `act.${e.action}` as MessageKey;
              const details = describeDetails(e);
              return (
                <li key={e.id} className="flex gap-4 px-5 py-3.5">
                  <div className={clsx("mt-0.5 flex size-8 shrink-0 items-center justify-center rounded-lg", tone)}>
                    <Icon className="size-4" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="text-sm text-slate-800">
                      <span className="font-medium text-slate-900">{actorLabel(e.actor, t)}</span>
                      <span className="text-slate-400"> · </span>
                      {t(label)}
                    </p>
                    {e.summary && (
                      <p className="mt-0.5 truncate text-[13px] text-slate-600">
                        {e.entity === "student" && e.entity_id && e.action !== "student.delete" ? (
                          <Link to={`/students/${e.entity_id}`} className="hover:text-brand-700 hover:underline">
                            {e.summary}
                          </Link>
                        ) : (
                          e.summary
                        )}
                      </p>
                    )}
                    {details && <p className="mt-0.5 truncate text-xs text-slate-400">{details}</p>}
                  </div>
                  <time className="shrink-0 text-xs whitespace-nowrap text-slate-400 tabular" dateTime={e.at}>
                    {formatDateTime(e.at, locale)}
                  </time>
                </li>
              );
            })}
          </ul>
        )}
        {data && data.total > 0 && <Pagination page={page} pageSize={50} total={data.total} onPage={setPage} />}
      </Card>
    </>
  );
}
