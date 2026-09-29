import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import clsx from "clsx";
import {
  Eye,
  EyeOff,
  MoreHorizontal,
  Pencil,
  Plus,
  Trash2,
  UserPlus,
  UsersRound,
} from "lucide-react";
import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { ConfirmDialog, Menu, Modal, useToast } from "../components/overlay";
import { AccountFormModal } from "../components/AccountForm";
import { Avatar, Badge, Button, Card, EmptyState, Field, Input, PageHeader, PageLoader, Switch, Textarea } from "../components/ui";
import { useI18n } from "../i18n";
import { api, ApiError } from "../lib/api";
import { errorMessage, useUser } from "../lib/auth";
import type { Group } from "../lib/types";

function AddGroupsModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { t } = useI18n();
  const toast = useToast();
  const qc = useQueryClient();
  const [names, setNames] = useState("");
  const [result, setResult] = useState<{ added: string[]; existing: string[]; invalid: string[] } | null>(null);
  const [error, setError] = useState<string | null>(null);

  const add = useMutation({
    mutationFn: () => api.post<{ added: string[]; existing: string[]; invalid: string[] }>("/api/groups", { names }),
    onSuccess: (r) => {
      qc.invalidateQueries({ queryKey: ["groups"] });
      qc.invalidateQueries({ queryKey: ["stats"] });
      if (!r.existing.length && !r.invalid.length) {
        toast.success(t("groups.result_added", { names: r.added.join(", ") }));
        close();
      } else {
        setResult(r);
        setNames(r.invalid.join("\n"));
      }
    },
    onError: (err) => {
      if (err instanceof ApiError && err.code === "invalid_names") setError(t("err.invalid_names"));
      else setError(errorMessage(err, t));
    },
  });

  const close = () => {
    setNames("");
    setResult(null);
    setError(null);
    onClose();
  };
  const submit = (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setResult(null);
    add.mutate();
  };

  return (
    <Modal
      open={open}
      onClose={close}
      title={t("groups.add")}
      footer={
        <>
          <Button variant="secondary" onClick={close}>
            {t("action.close")}
          </Button>
          <Button type="submit" form="add-groups" loading={add.isPending} disabled={!names.trim()}>
            {t("action.add")}
          </Button>
        </>
      }
    >
      <form id="add-groups" onSubmit={submit} className="space-y-4">
        <Field label={t("groups.names")} hint={t("groups.add_hint")} error={error}>
          {(id) => (
            <Textarea
              id={id}
              rows={7}
              value={names}
              onChange={(e) => setNames(e.target.value)}
              placeholder={"SE-24-01\nSE-24-02\nME-24-01"}
              className="font-mono text-[13px]"
            />
          )}
        </Field>
        {result && (
          <div className="space-y-1 rounded-lg bg-slate-50 p-3 text-sm">
            {result.added.length > 0 && <p className="text-emerald-700">{t("groups.result_added", { names: result.added.join(", ") })}</p>}
            {result.existing.length > 0 && <p className="text-slate-600">{t("groups.result_existing", { names: result.existing.join(", ") })}</p>}
            {result.invalid.length > 0 && <p className="text-red-600">{t("groups.result_invalid", { names: result.invalid.join(", ") })}</p>}
          </div>
        )}
      </form>
    </Modal>
  );
}

function RenameModal({ group, onClose }: { group: Group | null; onClose: () => void }) {
  const { t } = useI18n();
  const toast = useToast();
  const qc = useQueryClient();
  const [name, setName] = useState(group?.name ?? "");
  const [error, setError] = useState<string | null>(null);
  const save = useMutation({
    mutationFn: () => api.patch<Group>(`/api/groups/${group!.id}`, { name }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["groups"] });
      qc.invalidateQueries({ queryKey: ["students"] });
      toast.success(t("groups.saved"));
      onClose();
    },
    onError: (err) => setError(errorMessage(err, t)),
  });
  return (
    <Modal
      open={!!group}
      onClose={onClose}
      size="sm"
      title={t("groups.rename")}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            {t("action.cancel")}
          </Button>
          <Button type="submit" form="rename-group" loading={save.isPending}>
            {t("action.save")}
          </Button>
        </>
      }
    >
      <form
        id="rename-group"
        onSubmit={(e) => {
          e.preventDefault();
          setError(null);
          save.mutate();
        }}
      >
        <Field label={t("groups.name")} error={error}>
          {(id) => <Input id={id} value={name} onChange={(e) => setName(e.target.value)} required invalid={!!error} />}
        </Field>
      </form>
    </Modal>
  );
}

function GroupCard({
  group,
  isAdmin,
  onRename,
  onToggle,
  onDelete,
  onAddLeader,
}: {
  group: Group;
  isAdmin: boolean;
  onRename: () => void;
  onToggle: () => void;
  onDelete: () => void;
  onAddLeader: () => void;
}) {
  const { t } = useI18n();
  return (
    <Card className={clsx("flex flex-col", !group.is_active && "opacity-70")}>
      <div className="flex items-start justify-between gap-3 px-5 pt-5">
        <div>
          <div className="flex items-center gap-2">
            <h3 className="text-lg font-semibold tracking-tight text-slate-900">{group.name}</h3>
            {!group.is_active && <Badge tone="gray">{t("groups.hidden")}</Badge>}
          </div>
          <p className="mt-0.5 text-sm text-slate-500 tabular">{t("groups.students", { n: group.students })}</p>
        </div>
        {isAdmin && (
          <Menu
            label={t("action.edit")}
            trigger={<MoreHorizontal className="size-5" />}
            items={[
              { label: t("groups.add_leader"), icon: <UserPlus className="size-4" />, onSelect: onAddLeader },
              { label: t("groups.rename"), icon: <Pencil className="size-4" />, onSelect: onRename },
              group.is_active
                ? { label: t("groups.hide"), icon: <EyeOff className="size-4" />, onSelect: onToggle }
                : { label: t("groups.show"), icon: <Eye className="size-4" />, onSelect: onToggle },
              { label: t("action.delete"), icon: <Trash2 className="size-4" />, onSelect: onDelete, danger: true },
            ]}
          />
        )}
      </div>

      <div className="flex-1 px-5 py-4">
        <p className="mb-2 text-xs font-medium tracking-wide text-slate-400 uppercase">{t("groups.leaders")}</p>
        {group.leaders.length === 0 ? (
          <p className="text-sm text-slate-400">{t("groups.no_leader")}</p>
        ) : (
          <ul className="space-y-2">
            {group.leaders.map((l) => (
              <li key={l.id} className="flex items-center gap-2.5">
                <Avatar name={l.label} size="sm" />
                <div className="min-w-0 leading-tight">
                  <p className="truncate text-sm font-medium text-slate-800">{l.label}</p>
                  <p className="truncate font-mono text-xs text-slate-500">{l.username}</p>
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>

      <div className="flex flex-wrap items-center gap-x-4 gap-y-2 border-t border-slate-100 px-5 py-3 text-[13px] font-medium">
        <Link to={`/students?group_id=${group.id}`} className="inline-flex items-center gap-1.5 text-brand-700 hover:text-brand-800">
          <UsersRound className="size-3.5" />
          {t("groups.view_students")}
        </Link>
      </div>
    </Card>
  );
}

export function GroupsPage() {
  const { t } = useI18n();
  const user = useUser();
  const toast = useToast();
  const qc = useQueryClient();
  const [showHidden, setShowHidden] = useState(false);
  const [adding, setAdding] = useState(false);
  const [renaming, setRenaming] = useState<Group | null>(null);
  const [deleting, setDeleting] = useState<Group | null>(null);
  const [leaderFor, setLeaderFor] = useState<number | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ["groups", { hidden: showHidden }],
    queryFn: () => api.get<Group[]>("/api/groups", { include_inactive: showHidden || undefined }),
  });

  const refresh = () => {
    qc.invalidateQueries({ queryKey: ["groups"] });
    qc.invalidateQueries({ queryKey: ["stats"] });
  };
  const toggle = useMutation({
    mutationFn: (g: Group) => api.patch(`/api/groups/${g.id}`, { is_active: !g.is_active }),
    onSuccess: () => {
      refresh();
      toast.success(t("groups.saved"));
    },
    onError: (err) => toast.error(errorMessage(err, t)),
  });
  const remove = useMutation({
    mutationFn: (g: Group) => api.delete<{ deleted: boolean }>(`/api/groups/${g.id}`),
    onSuccess: (r) => {
      refresh();
      setDeleting(null);
      toast.success(r.deleted ? t("groups.deleted") : t("groups.hidden_instead"));
    },
    onError: (err) => toast.error(errorMessage(err, t)),
  });

  return (
    <>
      <PageHeader
        title={t("groups.title")}
        subtitle={t("groups.subtitle")}
        actions={
          user.is_admin && (
            <>
              <label className="mr-2 flex items-center gap-2.5 text-sm text-slate-600">
                <Switch checked={showHidden} onChange={setShowHidden} label={t("groups.show_hidden")} />
                {t("groups.show_hidden")}
              </label>
              <Button icon={<Plus className="size-4" />} onClick={() => setAdding(true)}>
                {t("groups.add")}
              </Button>
            </>
          )
        }
      />

      {isLoading ? (
        <PageLoader />
      ) : !data?.length ? (
        <Card>
          <EmptyState
            icon={<UsersRound className="size-6" />}
            title={t("groups.empty")}
            action={user.is_admin && <Button icon={<Plus className="size-4" />} onClick={() => setAdding(true)}>{t("groups.add")}</Button>}
          />
        </Card>
      ) : (
        <div className="grid gap-5 sm:grid-cols-2 xl:grid-cols-3">
          {data.map((g) => (
            <GroupCard
              key={g.id}
              group={g}
              isAdmin={user.is_admin}
              onRename={() => setRenaming(g)}
              onToggle={() => toggle.mutate(g)}
              onDelete={() => setDeleting(g)}
              onAddLeader={() => setLeaderFor(g.id)}
            />
          ))}
        </div>
      )}

      <AddGroupsModal open={adding} onClose={() => setAdding(false)} />
      <RenameModal key={renaming?.id ?? "none"} group={renaming} onClose={() => setRenaming(null)} />
      <AccountFormModal
        key={leaderFor ?? "none"}
        open={leaderFor !== null}
        onClose={() => setLeaderFor(null)}
        presetRole="leader"
        presetGroupId={leaderFor ?? undefined}
      />
      <ConfirmDialog
        open={!!deleting}
        onClose={() => setDeleting(null)}
        onConfirm={() => deleting && remove.mutate(deleting)}
        loading={remove.isPending}
        title={t("groups.delete_title", { name: deleting?.name ?? "" })}
        body={t("groups.delete_body")}
        confirmLabel={t("action.delete")}
      />
    </>
  );
}
