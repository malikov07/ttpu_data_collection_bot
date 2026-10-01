import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Award, Eye, FileImage, FileText, History, IdCard, ImageIcon, Pencil, Send, Trash2, Upload, UserRound } from "lucide-react";
import { useRef, useState, type FormEvent, type ReactNode } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { CertificateItem } from "../components/Certificates";
import { DocumentViewer, fileUrl } from "../components/DocumentViewer";
import { ConfirmDialog, useToast } from "../components/overlay";
import { StudentAvatar } from "../components/StudentBits";
import { Badge, Button, Card, CardHeader, EmptyState, ErrorBanner, Field, Input, PageLoader, Select } from "../components/ui";
import { useI18n, type MessageKey } from "../i18n";
import { api, ApiError } from "../lib/api";
import { errorMessage } from "../lib/auth";
import { actorLabel, formatDate, formatDateTime, formatPhone } from "../lib/format";
import type { DocKind, Group, StudentDetail } from "../lib/types";

function InfoRow({ label, children, stacked }: { label: string; children: ReactNode; stacked?: boolean }) {
  if (stacked) {
    return (
      <div className="px-5 py-3">
        <dt className="text-xs text-slate-500">{label}</dt>
        <dd className="mt-0.5 text-sm font-medium break-words text-slate-900">{children}</dd>
      </div>
    );
  }
  return (
    <div className="grid grid-cols-[minmax(0,1fr)_minmax(0,2fr)] gap-4 px-5 py-3.5">
      <dt className="text-sm break-words text-slate-500">{label}</dt>
      <dd className="text-sm font-medium break-words text-slate-900">{children}</dd>
    </div>
  );
}

// ------------------------------------------------------------------ edit forms

type Values = Record<string, string>;

function useSave(student: StudentDetail, onDone: () => void) {
  const { t } = useI18n();
  const toast = useToast();
  const qc = useQueryClient();
  const [error, setError] = useState<{ field?: string; message: string } | null>(null);
  const mutation = useMutation({
    mutationFn: (body: object) => api.patch<StudentDetail>(`/api/students/${student.id}`, body),
    onSuccess: (data) => {
      qc.setQueryData(["student", student.id], data);
      qc.invalidateQueries({ queryKey: ["students"] });
      qc.invalidateQueries({ queryKey: ["stats"] });
      toast.success(t("student.saved"));
      onDone();
    },
    onError: (err) => setError({ field: err instanceof ApiError ? err.field : undefined, message: errorMessage(err, t) }),
  });
  return { mutation, error, setError, errFor: (f: string) => (error?.field === f ? error.message : null) };
}

function FormFooter({ onCancel, loading }: { onCancel: () => void; loading: boolean }) {
  const { t } = useI18n();
  return (
    <div className="flex justify-end gap-2 border-t border-slate-100 bg-slate-50/60 px-5 py-3">
      <Button variant="secondary" onClick={onCancel}>
        {t("action.cancel")}
      </Button>
      <Button type="submit" loading={loading}>
        {t("action.save")}
      </Button>
    </div>
  );
}

function PersonalForm({ student, onDone }: { student: StudentDetail; onDone: () => void }) {
  const { t } = useI18n();
  const groups = useQuery({ queryKey: ["groups"], queryFn: () => api.get<Group[]>("/api/groups") });
  const [v, setV] = useState<Values>({
    last_name: student.last_name,
    first_name: student.first_name,
    middle_name: student.middle_name ?? "",
    birth_date: student.birth_date,
    gender: student.gender,
    phone: formatPhone(student.phone),
    group_id: String(student.group.id),
  });
  const { mutation, error, setError, errFor } = useSave(student, onDone);
  const set = (k: string) => (e: { target: { value: string } }) => setV((x) => ({ ...x, [k]: e.target.value }));
  const submit = (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    mutation.mutate({ ...v, group_id: Number(v.group_id) });
  };
  const text = (k: string, label: MessageKey, extra?: object) => (
    <Field label={t(label)} error={errFor(k)} hint={k === "middle_name" ? t("student.clear_hint") : undefined}>
      {(id) => <Input id={id} value={v[k]} onChange={set(k)} invalid={!!errFor(k)} {...extra} />}
    </Field>
  );
  return (
    <form onSubmit={submit}>
      <div className="grid gap-5 p-5 sm:grid-cols-3">
        {text("last_name", "student.last_name", { required: true })}
        {text("first_name", "student.first_name", { required: true })}
        {text("middle_name", "student.middle_name")}
        {text("birth_date", "student.birth_date", { type: "date", required: true })}
        <Field label={t("student.gender")}>
          {(id) => (
            <Select id={id} value={v.gender} onChange={set("gender")}>
              <option value="male">{t("gender.male")}</option>
              <option value="female">{t("gender.female")}</option>
            </Select>
          )}
        </Field>
        {text("phone", "student.phone", { type: "tel", required: true })}
        <Field label={t("student.group")} error={errFor("group_id")}>
          {(id) => (
            <Select id={id} value={v.group_id} onChange={set("group_id")}>
              {!groups.data?.some((g) => g.id === student.group.id) && <option value={student.group.id}>{student.group.name}</option>}
              {groups.data?.map((g) => (
                <option key={g.id} value={g.id}>
                  {g.name}
                </option>
              ))}
            </Select>
          )}
        </Field>
        {error && !error.field && <ErrorBanner>{error.message}</ErrorBanner>}
      </div>
      <FormFooter onCancel={onDone} loading={mutation.isPending} />
    </form>
  );
}

function IdentityForm({ student, onDone }: { student: StudentDetail; onDone: () => void }) {
  const { t } = useI18n();
  const d = student.document;
  const [v, setV] = useState<Values>({
    doc_type: d.type ?? "passport",
    doc_number: d.number ?? "",
    doc_expiry: d.expiry ?? "",
    pinfl: d.pinfl ?? "",
  });
  const { mutation, error, setError, errFor } = useSave(student, onDone);
  const set = (k: string) => (e: { target: { value: string } }) => setV((x) => ({ ...x, [k]: e.target.value }));
  const submit = (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    mutation.mutate({ ...v, doc_expiry: v.doc_expiry || null });
  };
  return (
    <form onSubmit={submit}>
      <div className="grid gap-5 p-5 sm:grid-cols-2">
        <Field label={t("student.doc_type")}>
          {(id) => (
            <Select id={id} value={v.doc_type} onChange={set("doc_type")}>
              <option value="passport">{t("doctype.passport")}</option>
              <option value="id_card">{t("doctype.id_card")}</option>
            </Select>
          )}
        </Field>
        <Field label={t("student.doc_number")} error={errFor("doc_number")}>
          {(id) => <Input id={id} className="font-mono uppercase" value={v.doc_number} onChange={set("doc_number")} invalid={!!errFor("doc_number")} />}
        </Field>
        <Field label={t("student.doc_expiry")}>{(id) => <Input id={id} type="date" value={v.doc_expiry} onChange={set("doc_expiry")} />}</Field>
        <Field label={t("student.pinfl")} error={errFor("pinfl")}>
          {(id) => <Input id={id} className="font-mono" inputMode="numeric" maxLength={14} value={v.pinfl} onChange={set("pinfl")} invalid={!!errFor("pinfl")} />}
        </Field>
        {error && !error.field && <ErrorBanner>{error.message}</ErrorBanner>}
      </div>
      <FormFooter onCancel={onDone} loading={mutation.isPending} />
    </form>
  );
}

// ------------------------------------------------------------------ files

const DOC_META: Record<DocKind, { title: MessageKey; hint: MessageKey; icon: ReactNode; accept: string }> = {
  passport: { title: "student.passport", hint: "student.upload_hint_passport", icon: <IdCard className="size-5" />, accept: "image/jpeg,image/png,image/webp" },
  photo: { title: "student.photo", hint: "student.upload_hint_photo", icon: <ImageIcon className="size-5" />, accept: "image/jpeg,image/png,image/webp" },
  cv: { title: "student.cv", hint: "student.upload_hint_cv", icon: <FileText className="size-5" />, accept: "application/pdf,image/jpeg,image/png,image/webp,.doc,.docx,.odt" },
};

function DocumentBlock({ student, kind }: { student: StudentDetail; kind: DocKind }) {
  const { t } = useI18n();
  const toast = useToast();
  const qc = useQueryClient();
  const input = useRef<HTMLInputElement>(null);
  const [viewing, setViewing] = useState<number | null>(null);
  const doc = student.documents[kind];
  const meta = DOC_META[kind];

  const upload = useMutation({
    mutationFn: (files: FileList) => {
      const form = new FormData();
      Array.from(files).forEach((f) => form.append("files", f));
      return api.post<StudentDetail>(`/api/students/${student.id}/documents/${kind}`, form);
    },
    onSuccess: (data) => {
      qc.setQueryData(["student", student.id], data);
      qc.invalidateQueries({ queryKey: ["students"] });
      toast.success(t("student.doc_replaced"));
    },
    onError: (err) => toast.error(errorMessage(err, t)),
  });

  return (
    <div className="p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className="flex size-10 items-center justify-center rounded-lg bg-slate-100 text-slate-600">{meta.icon}</div>
          <div>
            <p className="text-sm font-semibold text-slate-900">{t(meta.title)}</p>
            <p className="text-xs text-slate-500">{doc.present ? t("student.pages", { n: doc.pages.length }) : t("student.not_submitted")}</p>
          </div>
        </div>
        {student.can_edit && (
          <>
            <input
              ref={input}
              type="file"
              multiple={kind !== "photo"}
              accept={meta.accept}
              className="hidden"
              onChange={(e) => {
                if (e.target.files?.length) upload.mutate(e.target.files);
                e.target.value = "";
              }}
            />
            <Button variant="secondary" size="sm" loading={upload.isPending} icon={<Upload className="size-3.5" />} onClick={() => input.current?.click()}>
              {doc.present ? t("action.replace") : t("action.upload")}
            </Button>
          </>
        )}
      </div>
      {doc.pages.length > 0 && (
        <ul className="mt-4 grid gap-2 sm:grid-cols-2">
          {doc.pages.map((p) => (
            <li key={p.index}>
              <button
                type="button"
                onClick={() => setViewing(p.index)}
                className="group flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-left ring-1 ring-slate-200 transition hover:bg-brand-50/50 hover:ring-brand-200"
              >
                {p.mime?.startsWith("image/") ? (
                  <FileImage className="size-5 shrink-0 text-slate-400 group-hover:text-brand-600" />
                ) : (
                  <FileText className="size-5 shrink-0 text-slate-400 group-hover:text-brand-600" />
                )}
                <span className="min-w-0 flex-1 truncate text-sm text-slate-700">
                  {p.side ? t(`side.${p.side}` as MessageKey) : p.name || t("student.page", { n: p.index + 1 })}
                </span>
                <Eye className="size-4 shrink-0 text-slate-400 group-hover:text-brand-600" />
              </button>
            </li>
          ))}
        </ul>
      )}
      {student.can_edit && <p className="mt-3 text-xs text-slate-400">{t(meta.hint)}</p>}
      <DocumentViewer
        pages={doc.pages}
        url={(i, download) => fileUrl(student.id, kind, i, download)}
        index={viewing}
        onIndex={setViewing}
        onClose={() => setViewing(null)}
        title={t(meta.title)}
      />
    </div>
  );
}

// ------------------------------------------------------------------ history

function HistoryList({ student }: { student: StudentDetail }) {
  const { t, locale } = useI18n();
  if (!student.history.length) return <p className="px-5 py-6 text-sm text-slate-400">{t("student.no_history")}</p>;
  const label = (field: string) => {
    const key = `student.${field}` as MessageKey;
    return key in DOC_LABELS ? t(key) : field;
  };
  return (
    <ol className="space-y-5 px-5 py-5">
      {student.history.map((h, i) => {
        const changes = h.action === "student.edit" && h.details ? Object.entries(h.details as Record<string, [unknown, unknown]>) : [];
        return (
          <li key={i} className="relative pl-6">
            <span className="absolute top-1.5 left-0 size-2 rounded-full bg-brand-400 ring-4 ring-brand-50" />
            {i < student.history.length - 1 && <span className="absolute top-4 bottom-[-1.25rem] left-[3px] w-px bg-slate-200" />}
            <p className="text-sm text-slate-800">{t(`act.${h.action}` as MessageKey)}</p>
            {changes.map(([field, [from, to]]) => (
              <p key={field} className="mt-0.5 text-xs break-words text-slate-500">
                {label(field)}: <span className="line-through decoration-slate-300">{String(from ?? "—")}</span> → {String(to ?? "—")}
              </p>
            ))}
            <p className="mt-0.5 text-xs text-slate-400">
              {actorLabel(h.actor, t)} · {formatDateTime(h.at, locale)}
            </p>
          </li>
        );
      })}
    </ol>
  );
}

const DOC_LABELS: Record<string, true> = Object.fromEntries(
  ["student.last_name", "student.first_name", "student.middle_name", "student.birth_date", "student.gender", "student.phone", "student.group", "student.doc_type", "student.doc_number", "student.doc_expiry", "student.pinfl"].map((k) => [k, true]),
);

// ------------------------------------------------------------------ page

export function StudentDetailPage() {
  const { id } = useParams();
  const studentId = Number(id);
  const { t, locale } = useI18n();
  const navigate = useNavigate();
  const toast = useToast();
  const qc = useQueryClient();
  const [editing, setEditing] = useState<"personal" | "identity" | null>(null);
  const [confirmDelete, setConfirmDelete] = useState(false);

  const { data: student, isLoading, error } = useQuery({
    queryKey: ["student", studentId],
    queryFn: () => api.get<StudentDetail>(`/api/students/${studentId}`),
  });
  const remove = useMutation({
    mutationFn: () => api.delete(`/api/students/${studentId}`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["students"] });
      qc.invalidateQueries({ queryKey: ["stats"] });
      toast.success(t("student.deleted"));
      navigate("/students", { replace: true });
    },
    onError: (err) => toast.error(errorMessage(err, t)),
  });

  if (isLoading) return <PageLoader />;
  if (error || !student) {
    return (
      <Card>
        <EmptyState
          icon={<UserRound className="size-6" />}
          title={errorMessage(error, t)}
          action={
            <Link to="/students">
              <Button variant="secondary">{t("student.back")}</Button>
            </Link>
          }
        />
      </Card>
    );
  }

  const d = student.document;
  const expired = d.expiry ? new Date(`${d.expiry}T23:59:59`) < new Date() : false;
  const editButton = (section: "personal" | "identity") =>
    student.can_edit && editing !== section ? (
      <Button variant="secondary" size="sm" icon={<Pencil className="size-3.5" />} onClick={() => setEditing(section)}>
        {t("action.edit")}
      </Button>
    ) : null;

  return (
    <>
      <Link to="/students" className="mb-5 inline-flex items-center gap-1.5 text-sm font-medium text-slate-500 hover:text-slate-900">
        <ArrowLeft className="size-4" />
        {t("student.back")}
      </Link>

      <div className="mb-6 flex flex-col gap-5 sm:flex-row sm:items-end sm:justify-between">
        <div className="flex items-end gap-5">
          <StudentAvatar student={student} size="xl" />
          <div className="min-w-0 pb-1">
            <h1 className="text-2xl font-semibold tracking-tight text-slate-900">{student.full_name}</h1>
            <div className="mt-2 flex flex-wrap items-center gap-2 text-sm text-slate-500">
              <Badge tone="blue">{student.group.name}</Badge>
              <span>{t("student.age", { n: student.age })}</span>
              <span>·</span>
              <span>{t(`gender.${student.gender}`)}</span>
            </div>
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          {student.telegram.username && (
            <a href={`https://t.me/${student.telegram.username}`} target="_blank" rel="noreferrer">
              <Button variant="secondary" icon={<Send className="size-4" />}>
                {t("student.open_telegram")}
              </Button>
            </a>
          )}
          {student.can_delete && (
            <Button variant="danger-ghost" icon={<Trash2 className="size-4" />} onClick={() => setConfirmDelete(true)}>
              {t("action.delete")}
            </Button>
          )}
        </div>
      </div>

      {!student.can_edit && <div className="mb-6 rounded-lg bg-slate-100 px-4 py-2.5 text-sm text-slate-600">{t("student.view_only")}</div>}

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="space-y-6 lg:col-span-2">
          <Card>
            <CardHeader title={t("student.personal")} icon={<UserRound className="size-[18px]" />} actions={editButton("personal")} />
            {editing === "personal" ? (
              <PersonalForm student={student} onDone={() => setEditing(null)} />
            ) : (
              <dl className="divide-y divide-slate-100">
                <InfoRow label={t("student.last_name")}>{student.last_name}</InfoRow>
                <InfoRow label={t("student.first_name")}>{student.first_name}</InfoRow>
                <InfoRow label={t("student.middle_name")}>{student.middle_name || "—"}</InfoRow>
                <InfoRow label={t("student.birth_date")}>
                  {formatDate(student.birth_date, locale)} <span className="font-normal text-slate-400">· {t("student.age", { n: student.age })}</span>
                </InfoRow>
                <InfoRow label={t("student.gender")}>{t(`gender.${student.gender}`)}</InfoRow>
                <InfoRow label={t("student.phone")}>
                  <a href={`tel:${student.phone}`} className="tabular hover:text-brand-700">
                    {formatPhone(student.phone)}
                  </a>
                </InfoRow>
                <InfoRow label={t("student.group")}>{student.group.name}</InfoRow>
              </dl>
            )}
          </Card>

          <Card>
            <CardHeader title={t("student.identity")} icon={<IdCard className="size-[18px]" />} actions={editButton("identity")} />
            {editing === "identity" ? (
              <IdentityForm student={student} onDone={() => setEditing(null)} />
            ) : (
              <dl className="divide-y divide-slate-100">
                <InfoRow label={t("student.doc_type")}>{d.type ? t(`doctype.${d.type}`) : "—"}</InfoRow>
                <InfoRow label={t("student.doc_number")}>
                  <span className="font-mono">{d.number || "—"}</span>
                </InfoRow>
                <InfoRow label={t("student.doc_expiry")}>
                  {formatDate(d.expiry, locale)} {expired && <Badge tone="red" className="ml-1">{t("student.expired")}</Badge>}
                </InfoRow>
                <InfoRow label={t("student.pinfl")}>
                  <span className="font-mono tabular">{d.pinfl || "—"}</span>
                </InfoRow>
                <InfoRow label={t("student.nationality")}>{d.nationality || "—"}</InfoRow>
              </dl>
            )}
          </Card>

          <Card>
            <CardHeader title={t("student.documents")} icon={<FileText className="size-[18px]" />} />
            <div className="divide-y divide-slate-100">
              <DocumentBlock student={student} kind="passport" />
              <DocumentBlock student={student} kind="photo" />
              <DocumentBlock student={student} kind="cv" />
            </div>
          </Card>

          <Card>
            <CardHeader title={t("cert.title")} icon={<Award className="size-[18px]" />} />
            {student.certificates.length > 0 ? (
              <div className="divide-y divide-slate-100">
                {student.certificates.map((c) => (
                  <CertificateItem key={c.id} cert={c} studentId={student.id} canReview={student.can_edit} />
                ))}
              </div>
            ) : (
              <p className="px-5 py-6 text-sm text-slate-400">{t("cert.none")}</p>
            )}
          </Card>
        </div>

        <div className="space-y-6">
          <Card>
            <dl className="divide-y divide-slate-100">
              <InfoRow stacked label={t("student.telegram")}>
                {student.telegram.username ? `@${student.telegram.username}` : <span className="tabular">{student.telegram.id}</span>}
              </InfoRow>
              <InfoRow stacked label={t("student.registered")}>{formatDateTime(student.created_at, locale)}</InfoRow>
              <InfoRow stacked label={t("student.updated")}>{formatDateTime(student.updated_at, locale)}</InfoRow>
            </dl>
          </Card>
          <Card>
            <CardHeader title={t("student.history")} icon={<History className="size-[18px]" />} />
            <HistoryList student={student} />
          </Card>
        </div>
      </div>

      <ConfirmDialog
        open={confirmDelete}
        onClose={() => setConfirmDelete(false)}
        onConfirm={() => remove.mutate()}
        loading={remove.isPending}
        title={t("student.delete_title")}
        body={t("student.delete_body", { name: student.full_name })}
        confirmLabel={t("action.delete")}
      />
    </>
  );
}
