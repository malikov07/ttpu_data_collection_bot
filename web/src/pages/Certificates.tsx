import { keepPreviousData, useQuery } from "@tanstack/react-query";
import clsx from "clsx";
import { Award, Search, X } from "lucide-react";
import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { CERT_TYPES, CertificateItem } from "../components/Certificates";
import { Button, Card, EmptyState, Input, PageHeader, Pagination, Select, Spinner } from "../components/ui";
import { useI18n, type MessageKey } from "../i18n";
import { api } from "../lib/api";
import type { CertificatePage, CertStatus, Group } from "../lib/types";

const PAGE_SIZE = 20;
const TABS: { value: CertStatus | ""; label: MessageKey }[] = [
  { value: "pending", label: "cert.tab_pending" },
  { value: "approved", label: "cert.tab_approved" },
  { value: "rejected", label: "cert.tab_rejected" },
  { value: "", label: "cert.tab_all" },
];

export function CertificatesPage() {
  const { t } = useI18n();
  const [params, setParams] = useSearchParams();
  const [search, setSearch] = useState(params.get("q") ?? "");

  const filters = {
    // "pending" by default: the page is mostly a review queue.
    status: params.get("status") ?? "pending",
    type: params.get("type") ?? "",
    group_id: params.get("group_id") ?? "",
    q: params.get("q") ?? "",
    page: Number(params.get("page") || 1),
  };

  const update = (patch: Partial<Record<keyof typeof filters, string | number>>) => {
    const next = new URLSearchParams(params);
    for (const [k, v] of Object.entries(patch)) {
      if (v === undefined || v === null || (v === "" && k !== "status")) next.delete(k);
      else next.set(k, String(v));
    }
    if (!("page" in patch)) next.delete("page");
    setParams(next, { replace: true });
  };

  useEffect(() => {
    const id = setTimeout(() => search !== filters.q && update({ q: search }), 300);
    return () => clearTimeout(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [search]);

  const groups = useQuery({ queryKey: ["groups"], queryFn: () => api.get<Group[]>("/api/groups") });
  const { data, isLoading, isFetching } = useQuery({
    queryKey: ["certificates", filters],
    queryFn: () => api.get<CertificatePage>("/api/certificates", { ...filters, page_size: PAGE_SIZE }),
    placeholderData: keepPreviousData,
  });

  const hasFilters = Boolean(filters.q || filters.type || filters.group_id);
  const count = (status: CertStatus | "") =>
    data ? (status ? data.counts[status] : data.counts.pending + data.counts.approved + data.counts.rejected) : null;

  return (
    <>
      <PageHeader title={t("cert.title")} subtitle={t("cert.subtitle")} />

      <Card>
        <div className="flex gap-1 overflow-x-auto border-b border-slate-100 px-3 pt-2" role="tablist">
          {TABS.map((tab) => {
            const active = filters.status === tab.value;
            const n = count(tab.value);
            return (
              <button
                key={tab.value || "all"}
                type="button"
                role="tab"
                aria-selected={active}
                onClick={() => update({ status: tab.value })}
                className={clsx(
                  "-mb-px flex shrink-0 items-center gap-2 border-b-2 px-3 py-2.5 text-sm font-medium transition-colors",
                  active ? "border-brand-600 text-brand-700" : "border-transparent text-slate-500 hover:text-slate-800",
                )}
              >
                {t(tab.label)}
                {n !== null && (
                  <span
                    className={clsx(
                      "rounded-full px-1.5 text-[11px] tabular",
                      tab.value === "pending" && n > 0 ? "bg-amber-100 text-amber-800" : "bg-slate-100 text-slate-600",
                    )}
                  >
                    {n}
                  </span>
                )}
              </button>
            );
          })}
        </div>

        <div className="flex flex-col gap-3 border-b border-slate-100 p-4 lg:flex-row lg:items-center">
          <div className="relative flex-1">
            <Search className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-slate-400" />
            <Input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder={t("cert.search")}
              className="pl-9"
              aria-label={t("cert.search")}
            />
          </div>
          <div className="grid grid-cols-1 gap-3 sm:flex">
            {(groups.data?.length ?? 0) > 1 && (
              <Select value={filters.group_id} onChange={(e) => update({ group_id: e.target.value })} className="sm:w-40" aria-label={t("col.group")}>
                <option value="">{t("students.all_groups")}</option>
                {groups.data?.map((g) => (
                  <option key={g.id} value={g.id}>
                    {g.name}
                  </option>
                ))}
              </Select>
            )}
            <Select value={filters.type} onChange={(e) => update({ type: e.target.value })} className="sm:w-52" aria-label={t("cert.type")}>
              <option value="">{t("cert.all_types")}</option>
              {CERT_TYPES.map((ct) => (
                <option key={ct} value={ct}>
                  {t(`cert.type.${ct}`)}
                </option>
              ))}
            </Select>
            {hasFilters && (
              <Button
                variant="ghost"
                icon={<X className="size-4" />}
                onClick={() => {
                  setSearch("");
                  update({ q: "", type: "", group_id: "" });
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
          <EmptyState
            icon={<Award className="size-6" />}
            title={filters.status === "pending" && !hasFilters ? t("cert.empty_pending") : t("cert.empty")}
          />
        ) : (
          <ul className={clsx("divide-y divide-slate-100 transition-opacity", isFetching && "opacity-60")}>
            {data.items.map((c) => (
              <li key={c.id}>
                <CertificateItem cert={c} studentId={c.student!.id} canReview={!!c.can_review} />
              </li>
            ))}
          </ul>
        )}
        {data && data.total > 0 && (
          <Pagination page={filters.page} pageSize={PAGE_SIZE} total={data.total} onPage={(p) => update({ page: p })} />
        )}
      </Card>
    </>
  );
}
