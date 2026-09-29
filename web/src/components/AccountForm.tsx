import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import clsx from "clsx";
import { Check, Copy } from "lucide-react";
import { useState, type FormEvent } from "react";
import { useI18n } from "../i18n";
import { api, ApiError } from "../lib/api";
import { errorMessage, useConfig } from "../lib/auth";
import type { Account, Group, Role } from "../lib/types";
import { Modal } from "./overlay";
import { Button, Field, Input, Select } from "./ui";

const ROLES: Role[] = ["leader", "tutor", "admin"];

/** Shows a login + temporary password once, with copy buttons. */
export function CredentialsModal({
  open,
  onClose,
  title,
  body,
  username,
  password,
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  body: string;
  username: string;
  password: string;
}) {
  const { t } = useI18n();
  const [copied, setCopied] = useState(false);
  const copy = async () => {
    await navigator.clipboard.writeText(`${t("accounts.username")}: ${username}\n${t("accounts.temp_password")}: ${password}`);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };
  return (
    <Modal
      open={open}
      onClose={onClose}
      title={title}
      description={body}
      footer={
        <>
          <Button variant="secondary" onClick={copy} icon={copied ? <Check className="size-4" /> : <Copy className="size-4" />}>
            {copied ? t("action.copied") : t("action.copy")}
          </Button>
          <Button onClick={onClose}>{t("action.close")}</Button>
        </>
      }
    >
      <dl className="grid grid-cols-[auto_1fr] gap-x-6 gap-y-2 rounded-lg bg-slate-50 p-4 text-sm">
        <dt className="text-slate-500">{t("accounts.username")}</dt>
        <dd className="font-mono font-semibold text-slate-900">{username}</dd>
        <dt className="text-slate-500">{t("accounts.temp_password")}</dt>
        <dd className="font-mono font-semibold tracking-wide text-slate-900 select-all">{password}</dd>
      </dl>
    </Modal>
  );
}

/** "New account" dialog, shared by the Accounts and Groups pages. */
export function AccountFormModal({
  open,
  onClose,
  presetRole,
  presetGroupId,
}: {
  open: boolean;
  onClose: () => void;
  presetRole?: Role;
  presetGroupId?: number;
}) {
  const { t } = useI18n();
  const qc = useQueryClient();
  const config = useConfig();
  const groups = useQuery({ queryKey: ["groups"], queryFn: () => api.get<Group[]>("/api/groups"), enabled: open });
  const [username, setUsername] = useState("");
  const [name, setName] = useState("");
  const [role, setRole] = useState<Role>(presetRole ?? "leader");
  const [groupId, setGroupId] = useState(presetGroupId ? String(presetGroupId) : "");
  const [error, setError] = useState<{ field?: string; message: string } | null>(null);
  const [created, setCreated] = useState<Account | null>(null);

  const create = useMutation({
    mutationFn: () =>
      api.post<Account>("/api/accounts", {
        username,
        display_name: name || null,
        roles: [{ role, group_id: role === "leader" ? Number(groupId) || null : null }],
      }),
    onSuccess: (account) => {
      qc.invalidateQueries({ queryKey: ["accounts"] });
      qc.invalidateQueries({ queryKey: ["groups"] });
      setCreated(account);
    },
    onError: (err) => setError({ field: err instanceof ApiError ? err.field : undefined, message: errorMessage(err, t) }),
  });

  const close = () => {
    setUsername("");
    setName("");
    setRole(presetRole ?? "leader");
    setGroupId(presetGroupId ? String(presetGroupId) : "");
    setError(null);
    setCreated(null);
    onClose();
  };
  const submit = (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    create.mutate();
  };
  const errFor = (f: string) => (error?.field === f ? error.message : null);

  if (created) {
    return (
      <CredentialsModal
        open={open}
        onClose={close}
        title={t("accounts.created_title")}
        body={t("accounts.created_body", { name: created.label, bot: config.data?.bot_username ?? "bot" })}
        username={created.username}
        password={created.temporary_password ?? ""}
      />
    );
  }

  return (
    <Modal
      open={open}
      onClose={close}
      title={t("accounts.add")}
      footer={
        <>
          <Button variant="secondary" onClick={close}>
            {t("action.cancel")}
          </Button>
          <Button type="submit" form="account-form" loading={create.isPending}>
            {t("action.add")}
          </Button>
        </>
      }
    >
      <form id="account-form" onSubmit={submit} className="space-y-5">
        <Field label={t("accounts.username")} hint={t("err.invalid_username")} error={errFor("username")}>
          {(id) => (
            <Input
              id={id}
              required
              autoComplete="off"
              autoCapitalize="none"
              spellCheck={false}
              value={username}
              onChange={(e) => setUsername(e.target.value.toLowerCase())}
              placeholder="j.rahimov"
              invalid={!!errFor("username")}
            />
          )}
        </Field>
        <Field label={t("accounts.name")}>{(id) => <Input id={id} value={name} onChange={(e) => setName(e.target.value)} />}</Field>
        <fieldset>
          <legend className="mb-1.5 text-sm font-medium text-slate-700">{t("accounts.role")}</legend>
          <div className="grid gap-2 sm:grid-cols-3">
            {ROLES.map((r) => (
              <label
                key={r}
                className={clsx(
                  "cursor-pointer rounded-lg p-3 ring-1 transition",
                  role === r ? "bg-brand-50 ring-2 ring-brand-600" : "ring-slate-200 hover:bg-slate-50",
                )}
              >
                <input type="radio" name="role" value={r} checked={role === r} onChange={() => setRole(r)} className="sr-only" />
                <span className="block text-sm font-medium text-slate-900">{t(`role.${r}`)}</span>
                <span className="mt-0.5 block text-xs leading-snug text-slate-500">{t(`accounts.role_${r}_hint`)}</span>
              </label>
            ))}
          </div>
          {errFor("roles") && <p className="mt-1.5 text-[13px] text-red-600">{errFor("roles")}</p>}
        </fieldset>
        {role === "leader" && (
          <Field label={t("accounts.group")}>
            {(id) => (
              <Select id={id} required value={groupId} onChange={(e) => setGroupId(e.target.value)}>
                <option value="" disabled>
                  —
                </option>
                {groups.data?.map((g) => (
                  <option key={g.id} value={g.id}>
                    {g.name}
                  </option>
                ))}
              </Select>
            )}
          </Field>
        )}
        {error && !error.field && <p className="text-sm text-red-600">{error.message}</p>}
      </form>
    </Modal>
  );
}
