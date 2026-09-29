import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { KeyRound, MoreHorizontal, Pause, Play, Plus, ShieldCheck, Trash2, Unlink } from "lucide-react";
import { useState } from "react";
import { AccountFormModal, CredentialsModal } from "../components/AccountForm";
import { ConfirmDialog, Menu, useToast, type MenuItem } from "../components/overlay";
import { Avatar, Badge, Button, Card, EmptyState, PageHeader, PageLoader } from "../components/ui";
import { useI18n } from "../i18n";
import { api } from "../lib/api";
import { errorMessage, useUser } from "../lib/auth";
import { relativeTime } from "../lib/format";
import type { Account, Role } from "../lib/types";

const ROLE_TONE: Record<Role, "violet" | "blue" | "green"> = { admin: "violet", tutor: "blue", leader: "green" };

export function AccountsPage() {
  const { t, locale } = useI18n();
  const me = useUser();
  const toast = useToast();
  const qc = useQueryClient();
  const [adding, setAdding] = useState(false);
  const [removing, setRemoving] = useState<Account | null>(null);
  const [reset, setReset] = useState<{ account: Account; password: string } | null>(null);

  const { data, isLoading } = useQuery({ queryKey: ["accounts"], queryFn: () => api.get<Account[]>("/api/accounts") });
  const refresh = () => {
    qc.invalidateQueries({ queryKey: ["accounts"] });
    qc.invalidateQueries({ queryKey: ["groups"] });
  };
  const patch = useMutation({
    mutationFn: ({ id, body }: { id: number; body: object }) => api.patch<Account>(`/api/accounts/${id}`, body),
    onSuccess: () => {
      refresh();
      toast.success(t("accounts.saved"));
    },
    onError: (err) => toast.error(errorMessage(err, t)),
  });
  const resetPassword = useMutation({
    mutationFn: (a: Account) => api.post<{ temporary_password: string }>(`/api/accounts/${a.id}/reset-password`),
    onSuccess: (r, a) => {
      refresh();
      setReset({ account: a, password: r.temporary_password });
    },
    onError: (err) => toast.error(errorMessage(err, t)),
  });
  const unlink = useMutation({
    mutationFn: (a: Account) => api.post(`/api/accounts/${a.id}/unlink-telegram`),
    onSuccess: () => {
      refresh();
      toast.success(t("accounts.saved"));
    },
  });
  const remove = useMutation({
    mutationFn: (a: Account) => api.delete(`/api/accounts/${a.id}`),
    onSuccess: () => {
      refresh();
      setRemoving(null);
      toast.success(t("accounts.deleted"));
    },
    onError: (err) => toast.error(errorMessage(err, t)),
  });

  const items = (a: Account): MenuItem[] => {
    if (a.id === me.id) return [];
    const list: MenuItem[] = [{ label: t("accounts.reset_password"), icon: <KeyRound className="size-4" />, onSelect: () => resetPassword.mutate(a) }];
    if (a.telegram) list.push({ label: t("accounts.unlink"), icon: <Unlink className="size-4" />, onSelect: () => unlink.mutate(a) });
    list.push(
      a.is_active
        ? { label: t("accounts.disable"), icon: <Pause className="size-4" />, onSelect: () => patch.mutate({ id: a.id, body: { is_active: false } }) }
        : { label: t("accounts.enable"), icon: <Play className="size-4" />, onSelect: () => patch.mutate({ id: a.id, body: { is_active: true } }) },
      { label: t("action.delete"), icon: <Trash2 className="size-4" />, onSelect: () => setRemoving(a), danger: true },
    );
    return list;
  };

  return (
    <>
      <PageHeader
        title={t("accounts.title")}
        subtitle={t("accounts.subtitle")}
        actions={
          <Button icon={<Plus className="size-4" />} onClick={() => setAdding(true)}>
            {t("accounts.add")}
          </Button>
        }
      />
      <Card>
        {isLoading ? (
          <PageLoader />
        ) : !data?.length ? (
          <EmptyState icon={<ShieldCheck className="size-6" />} title={t("accounts.empty")} />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[760px] text-sm">
              <thead className="bg-slate-50/80 text-left text-xs font-medium text-slate-500">
                <tr>
                  <th className="py-3 pr-4 pl-5">{t("accounts.col_person")}</th>
                  <th className="px-4 py-3">{t("accounts.col_roles")}</th>
                  <th className="px-4 py-3">{t("accounts.col_telegram")}</th>
                  <th className="px-4 py-3">{t("accounts.col_last_login")}</th>
                  <th className="w-12 py-3 pr-5" />
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {data.map((a) => (
                  <tr key={a.id} className={a.is_active ? "hover:bg-slate-50/60" : "bg-slate-50/50 text-slate-400"}>
                    <td className="py-3 pr-4 pl-5">
                      <div className="flex items-center gap-3">
                        <Avatar name={a.label} />
                        <div className="min-w-0 leading-tight">
                          <p className="truncate font-medium text-slate-900">{a.label}</p>
                          <p className="truncate font-mono text-xs text-slate-500">{a.username}</p>
                        </div>
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex flex-wrap items-center gap-1.5">
                        {a.roles.map((r, i) => (
                          <Badge key={i} tone={ROLE_TONE[r.role]}>
                            {t(`role.${r.role}`)}
                            {r.group && ` · ${r.group.name}`}
                          </Badge>
                        ))}
                        {!a.is_active && <Badge tone="gray">{t("accounts.disabled")}</Badge>}
                        {a.is_active && a.must_change_password && <Badge tone="amber">{t("accounts.pending_password")}</Badge>}
                      </div>
                    </td>
                    <td className="px-4 py-3 text-slate-600">
                      {a.telegram ? (a.telegram.username ? `@${a.telegram.username}` : a.telegram.id) : <span className="text-slate-400">{t("accounts.telegram_none")}</span>}
                    </td>
                    <td className="px-4 py-3 whitespace-nowrap text-slate-500">
                      {a.last_login_at ? relativeTime(a.last_login_at, t, locale) : t("accounts.never")}
                    </td>
                    <td className="py-3 pr-5 text-right">
                      {items(a).length > 0 && <Menu label={t("action.edit")} trigger={<MoreHorizontal className="size-5" />} items={items(a)} />}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      <AccountFormModal open={adding} onClose={() => setAdding(false)} />
      {reset && (
        <CredentialsModal
          open
          onClose={() => setReset(null)}
          title={t("accounts.reset_title")}
          body={t("accounts.reset_body", { name: reset.account.label })}
          username={reset.account.username}
          password={reset.password}
        />
      )}
      <ConfirmDialog
        open={!!removing}
        onClose={() => setRemoving(null)}
        onConfirm={() => removing && remove.mutate(removing)}
        loading={remove.isPending}
        title={t("accounts.delete_title")}
        body={removing ? t("accounts.delete_body", { name: removing.label }) : ""}
        confirmLabel={t("action.delete")}
      />
    </>
  );
}
