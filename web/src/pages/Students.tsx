import { keepPreviousData, useQuery } from "@tanstack/react-query";
import clsx from "clsx";
import { ArrowDown, ArrowUp, ChevronsUpDown, Download, GraduationCap, Search, X } from "lucide-react";
import { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { DocPills, StudentAvatar } from "../components/StudentBits";
import { Badge, Button, Card, EmptyState, Input, PageHeader, Pagination, Select, Spinner } from "../components/ui";
import { useI18n, type MessageKey } from "../i18n";
import { api, withQuery } from "../lib/api";
import { formatDate, formatPhone, relativeTime } from "../lib/format";
import type { Group, Page, Student } from "../lib/types";

type SortKey = "name" | "group" | "birth_date" | "updated" | "created";
const PAGE_SIZE = 25;

function useDebounced<T>(value: T, ms = 300): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const id = setTimeout(() => setDebounced(value), ms);
    return () => clearTimeout(id);
  }, [value, ms]);
  return debounced;
}

export function StudentsPage() {
  const { t, locale, lang } = useI18n();
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const [search, setSearch] = useState(params.get("q") ?? "");
  const q = useDebounced(search);

  const filters = {
    q: params.get("q") ?? "",
    group_id: params.get("group_id") ?? "",
    gender: params.get("gender") ?? "",
    docs: params.get("docs") ?? "",
    sort: (params.get("sort") as SortKey) || "name",
    order: (params.get("order") as "asc" | "desc") || "asc",
    page: Number(params.get("page") || 1),
  };

  const update = (patch: Partial<Record<keyof typeof filters, string | number>>, resetPage = true) => {
    const next = new URLSearchParams(params);
    for (const [k, v] of Object.entries(patch)) {
      if (v === "" || v === undefined || v === null) next.delete(k);
      else next.set(k, String(v));
    }
    if (resetPage && !("page" in patch)) next.delete("page");
    setParams(next, { replace: true });
  };

  useEffect(() => {
    if (q !== filters.q) update({ q });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [q]);

  const groups = useQuery({ queryKey: ["groups"], queryFn: () => api.get<Group[]>("/api/groups") });
  const { data, isFetching, isLoading } = useQuery({
    queryKey: ["students", filters],
    queryFn: () => api.get<Page<Student>>("/api/students", { ...filters, page_size: PAGE_SIZE }),
    placeholderData: keepPreviousData,
  });

  const hasFilters = Boolean(filters.q || filters.group_id || filters.gender || filters.docs);
  const showGroupFilter = (groups.data?.length ?? 0) > 1;
  const exportUrl = withQuery("/api/export/students.xlsx", {
    lang,
    q: filters.q,
    group_id: filters.group_id,
    gender: filters.gender,
    docs: filters.docs,
  });

  const sortHeader = (key: SortKey, label: MessageKey, className?: string) => {
    const active = filters.sort === key;
    const Icon = !active ? ChevronsUpDown : filters.order === "asc" ? ArrowUp : ArrowDown;
    return (
      <th scope="col" className={clsx("px-4 py-3 text-left", className)}>
        <button
          type="button"
          className={clsx("inline-flex items-center gap-1 hover:text-slate-900", active && "text-slate-900")}
          onClick={() => update({ sort: key, order: active && filters.order === "asc" ? "desc" : "asc" })}
        >
          {t(label)}
          <Icon className={clsx("size-3.5", !active && "opacity-40")} />
        </button>
      </th>
    );
  };

  return (
    <>
      <PageHeader
        title={t("students.title")}
        subtitle={data ? t("students.count", { n: data.total.toLocaleString() }) : " "}
        actions={
          <a href={exportUrl} download>
            <Button variant="secondary" icon={<Download className="size-4" />}>
              {t("action.export")}
            </Button>
          </a>
        }
      />

      <Card>
        <div className="flex flex-col gap-3 border-b border-slate-100 p-4 lg:flex-row lg:items-center">
          <div className="relative flex-1">
            <Search className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-slate-400" />
            <Input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder={t("students.search")}
              className="pl-9"
              aria-label={t("students.search")}
            />
          </div>
          <div className="grid grid-cols-1 gap-3 sm:flex">
            {showGroupFilter && (
              <Select value={filters.group_id} onChange={(e) => update({ group_id: e.target.value })} className="sm:w-40" aria-label={t("col.group")}>
                <option value="">{t("students.all_groups")}</option>
                {groups.data?.map((g) => (
                  <option key={g.id} value={g.id}>
                    {g.name}
                  </option>
                ))}
              </Select>
            )}
            <Select value={filters.gender} onChange={(e) => update({ gender: e.target.value })} className="sm:w-40" aria-label={t("student.gender")}>
              <option value="">{t("students.all_genders")}</option>
              <option value="male">{t("gender.male")}</option>
              <option value="female">{t("gender.female")}</option>
            </Select>
            <Select value={filters.docs} onChange={(e) => update({ docs: e.target.value })} className="sm:w-52" aria-label={t("col.documents")}>
              <option value="">{t("students.all_docs")}</option>
              <option value="complete">{t("students.docs_complete")}</option>
              <option value="missing">{t("students.docs_missing")}</option>
            </Select>
            {hasFilters && (
              <Button
                variant="ghost"
                icon={<X className="size-4" />}
                onClick={() => {
                  setSearch("");
                  setParams(new URLSearchParams(), { replace: true });
                }}
              >
                {t("action.clear_filters")}
              </Button>
            )}
          </div>
        </div>

        {isLoading ? (
          <div className="flex h-64 items-center justify-center">
            <Spinner />
          </div>
        ) : !data || data.items.length === 0 ? (
          <EmptyState icon={<GraduationCap className="size-6" />} title={hasFilters ? t("students.empty") : t("students.empty_all")} />
        ) : (
          <div className={clsx("transition-opacity", isFetching && "opacity-60")}>
            {/* Phones: one card per student */}
            <ul className="divide-y divide-slate-100 md:hidden">
              {data.items.map((s) => (
                <li key={s.id}>
                  <button type="button" onClick={() => navigate(`/students/${s.id}`)} className="w-full px-4 py-3.5 text-left active:bg-slate-50">
                    <div className="flex items-start gap-3">
                      <StudentAvatar student={s} />
                      <div className="min-w-0 flex-1">
                        <div className="flex items-start justify-between gap-3">
                          <p className="font-medium text-slate-900">{s.full_name}</p>
                          <Badge tone="blue">{s.group.name}</Badge>
                        </div>
                        <p className="mt-0.5 text-[13px] text-slate-500 tabular">
                          {formatPhone(s.phone)} · {t(`gender.${s.gender}`)}
                        </p>
                        <div className="mt-2">
                          <DocPills student={s} />
                        </div>
                      </div>
                    </div>
                  </button>
                </li>
              ))}
            </ul>
            <div className="hidden overflow-x-auto md:block">
            <table className="w-full min-w-[760px] text-sm">
              <thead className="bg-slate-50/80 text-xs font-medium text-slate-500">
                <tr>
                  {sortHeader("name", "col.name", "pl-5")}
                  {sortHeader("group", "col.group")}
                  <th scope="col" className="px-4 py-3 text-left">{t("col.phone")}</th>
                  {sortHeader("birth_date", "col.birth_date", "hidden md:table-cell")}
                  <th scope="col" className="hidden px-4 py-3 text-left xl:table-cell">{t("col.document")}</th>
                  <th scope="col" className="px-4 py-3 text-left">{t("col.documents")}</th>
                  {sortHeader("updated", "col.updated", "hidden lg:table-cell pr-5")}
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {data.items.map((s) => (
                  <tr
                    key={s.id}
                    onClick={() => navigate(`/students/${s.id}`)}
                    className="cursor-pointer transition-colors hover:bg-brand-50/40"
                  >
                    <td className="py-3 pr-4 pl-5">
                      <div className="flex items-center gap-3">
                        <StudentAvatar student={s} size="sm" />
                        <div className="min-w-0">
                          <p className="font-medium text-slate-900">{s.full_name}</p>
                          <p className="text-xs text-slate-500">
                            {t(`gender.${s.gender}`)}
                            {s.telegram.username && <> · @{s.telegram.username}</>}
                          </p>
                        </div>
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      <Badge tone="blue">{s.group.name}</Badge>
                    </td>
                    <td className="px-4 py-3 whitespace-nowrap text-slate-700 tabular">{formatPhone(s.phone)}</td>
                    <td className="hidden px-4 py-3 whitespace-nowrap text-slate-700 tabular md:table-cell">
                      {formatDate(s.birth_date, locale)} <span className="text-slate-400">· {s.age}</span>
                    </td>
                    <td className="hidden px-4 py-3 whitespace-nowrap xl:table-cell">
                      <span className="font-mono text-[13px] text-slate-700">{s.document.number || "—"}</span>
                    </td>
                    <td className="px-4 py-3">
                      <DocPills student={s} />
                    </td>
                    <td className="hidden py-3 pr-5 pl-4 whitespace-nowrap text-slate-500 lg:table-cell">
                      {relativeTime(s.updated_at, t, locale)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            </div>
          </div>
        )}
        {data && data.total > 0 && (
          <Pagination page={filters.page} pageSize={PAGE_SIZE} total={data.total} onPage={(p) => update({ page: p }, false)} />
        )}
      </Card>
    </>
  );
}
