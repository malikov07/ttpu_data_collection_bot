import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Award, CheckCircle2, Clock3, Eye, FileImage, FileText, XCircle } from "lucide-react";
import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { useI18n, type Translate } from "../i18n";
import { api } from "../lib/api";
import { errorMessage } from "../lib/auth";
import { actorLabel, formatDateTime } from "../lib/format";
import type { Certificate, CertStatus, CertType } from "../lib/types";
import { certificateFileUrl, DocumentViewer } from "./DocumentViewer";
import { Modal, useToast } from "./overlay";
import { Badge, Button, Field, Textarea } from "./ui";

export const CERT_TYPES: CertType[] = ["ielts", "toefl", "sat", "duolingo", "cefr", "national", "olympiad", "other"];
const DESCRIBED: CertType[] = ["national", "olympiad", "other"];

/** "IELTS 7.5", "National certificate: Mathematics A+" */
export function certLabel(t: Translate, c: Pick<Certificate, "type" | "result">): string {
  return `${t(`cert.type.${c.type}`)}${DESCRIBED.includes(c.type) ? ": " : " "}${c.result}`;
}

const STATUS = {
  pending: { tone: "amber", icon: Clock3 },
  approved: { tone: "green", icon: CheckCircle2 },
  rejected: { tone: "red", icon: XCircle },
} as const;

export function CertStatusBadge({ status }: { status: CertStatus }) {
  const { t } = useI18n();
  const { tone, icon: Icon } = STATUS[status];
  return (
    <Badge tone={tone}>
      <Icon className="size-3" />
      {t(`cert.status.${status}`)}
    </Badge>
  );
}

function useReview(cert: Certificate, studentId: number, onDone?: () => void) {
  const { t } = useI18n();
  const toast = useToast();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { status: "approved" | "rejected"; note?: string }) =>
      api.post<Certificate>(`/api/certificates/${cert.id}/review`, body),
    onSuccess: (data) => {
      qc.invalidateQueries({ queryKey: ["certificates"] });
      qc.invalidateQueries({ queryKey: ["student", studentId] });
      qc.invalidateQueries({ queryKey: ["stats"] });
      toast.success(t(data.status === "approved" ? "cert.approved_toast" : "cert.rejected_toast"));
      onDone?.();
    },
    onError: (err) => toast.error(errorMessage(err, t)),
  });
}

function RejectDialog({ cert, studentId, open, onClose }: { cert: Certificate; studentId: number; open: boolean; onClose: () => void }) {
  const { t } = useI18n();
  const [note, setNote] = useState(cert.note ?? "");
  const review = useReview(cert, studentId, onClose);
  const submit = (e: FormEvent) => {
    e.preventDefault();
    review.mutate({ status: "rejected", note });
  };
  return (
    <Modal
      open={open}
      onClose={onClose}
      title={t("cert.reject_title")}
      description={certLabel(t, cert)}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            {t("action.cancel")}
          </Button>
          <Button variant="danger" type="submit" form={`reject-${cert.id}`} loading={review.isPending}>
            {t("cert.reject")}
          </Button>
        </>
      }
    >
      <form id={`reject-${cert.id}`} onSubmit={submit}>
        <Field label={t("cert.reason")} hint={t("cert.reason_hint")}>
          {(id) => <Textarea id={id} rows={3} maxLength={500} value={note} onChange={(e) => setNote(e.target.value)} />}
        </Field>
      </form>
    </Modal>
  );
}

/** One certificate: what it is, its files, the review, and Accept / Reject. */
export function CertificateItem({ cert, studentId, canReview }: { cert: Certificate; studentId: number; canReview: boolean }) {
  const { t, locale } = useI18n();
  const [viewing, setViewing] = useState<number | null>(null);
  const [rejecting, setRejecting] = useState(false);
  const review = useReview(cert, studentId);
  const title = certLabel(t, cert);

  return (
    <div className="flex flex-col gap-3 p-5 sm:flex-row sm:items-start">
      <div className="hidden size-10 shrink-0 items-center justify-center rounded-lg bg-brand-50 text-brand-700 sm:flex">
        <Award className="size-5" />
      </div>
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2">
          <p className="text-sm font-semibold break-words text-slate-900">{title}</p>
          <CertStatusBadge status={cert.status} />
        </div>
        {cert.student && (
          <p className="mt-0.5 text-sm text-slate-600">
            <Link to={`/students/${cert.student.id}`} className="font-medium hover:text-brand-700">
              {cert.student.full_name}
            </Link>{" "}
            · {cert.student.group.name}
          </p>
        )}
        <p className="mt-0.5 text-xs text-slate-500">
          {t("cert.sent_at", { at: formatDateTime(cert.created_at, locale) })}
          {cert.reviewed_by && cert.reviewed_at && cert.status !== "pending" && (
            <> · {t("cert.reviewed", { who: actorLabel(cert.reviewed_by, t), at: formatDateTime(cert.reviewed_at, locale) })}</>
          )}
        </p>
        {cert.status === "rejected" && cert.note && (
          <p className="mt-2 rounded-md bg-red-50/70 px-3 py-2 text-[13px] break-words text-red-800">
            {t("cert.reason")}: {cert.note}
          </p>
        )}
        <div className="mt-3 flex flex-wrap gap-2">
          {cert.files.map((f) => (
            <button
              key={f.index}
              type="button"
              onClick={() => setViewing(f.index)}
              className="group inline-flex max-w-full items-center gap-2 rounded-lg px-3 py-1.5 text-left text-[13px] text-slate-700 ring-1 ring-slate-200 transition hover:bg-brand-50/50 hover:ring-brand-200"
            >
              {f.mime?.startsWith("image/") ? (
                <FileImage className="size-4 shrink-0 text-slate-400 group-hover:text-brand-600" />
              ) : (
                <FileText className="size-4 shrink-0 text-slate-400 group-hover:text-brand-600" />
              )}
              <span className="truncate">{f.name || t("student.page", { n: f.index + 1 })}</span>
              <Eye className="size-3.5 shrink-0 text-slate-400 group-hover:text-brand-600" />
            </button>
          ))}
        </div>
      </div>
      {canReview && (
        <div className="flex shrink-0 gap-2 sm:flex-col">
          {cert.status !== "approved" && (
            <Button
              size="sm"
              icon={<CheckCircle2 className="size-3.5" />}
              loading={review.isPending}
              onClick={() => review.mutate({ status: "approved" })}
            >
              {t("cert.approve")}
            </Button>
          )}
          {cert.status !== "rejected" && (
            <Button variant="secondary" size="sm" icon={<XCircle className="size-3.5" />} onClick={() => setRejecting(true)}>
              {t("cert.reject")}
            </Button>
          )}
        </div>
      )}
      <DocumentViewer
        pages={cert.files}
        url={(i, download) => certificateFileUrl(cert.id, i, download)}
        index={viewing}
        onIndex={setViewing}
        onClose={() => setViewing(null)}
        title={title}
      />
      {rejecting && <RejectDialog cert={cert} studentId={studentId} open onClose={() => setRejecting(false)} />}
    </div>
  );
}
