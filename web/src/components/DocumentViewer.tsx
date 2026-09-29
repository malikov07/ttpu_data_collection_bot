import { ChevronLeft, ChevronRight, Download, FileText } from "lucide-react";
import { useEffect, useState } from "react";
import { useI18n } from "../i18n";
import type { DocKind, DocumentInfo } from "../lib/types";
import { Modal } from "./overlay";
import { Button, IconButton, Spinner } from "./ui";

export function fileUrl(studentId: number, kind: DocKind, index: number, download = false) {
  return `/api/students/${studentId}/documents/${kind}/${index}${download ? "?download=true" : ""}`;
}

/** Previews one file of a document (images and PDFs inline), with paging. */
export function DocumentViewer({
  studentId,
  kind,
  doc,
  index,
  onIndex,
  onClose,
  title,
}: {
  studentId: number;
  kind: DocKind;
  doc: DocumentInfo;
  index: number | null;
  onIndex: (i: number) => void;
  onClose: () => void;
  title: string;
}) {
  const { t } = useI18n();
  const [blob, setBlob] = useState<{ url: string; type: string } | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    if (index === null) return;
    let url: string | null = null;
    let cancelled = false;
    setBlob(null);
    setFailed(false);
    fetch(fileUrl(studentId, kind, index), { credentials: "same-origin" })
      .then((r) => (r.ok ? r.blob() : Promise.reject(new Error(String(r.status)))))
      .then((b) => {
        if (cancelled) return;
        url = URL.createObjectURL(b);
        setBlob({ url, type: b.type });
      })
      .catch(() => !cancelled && setFailed(true));
    return () => {
      cancelled = true;
      if (url) URL.revokeObjectURL(url);
    };
  }, [studentId, kind, index]);

  if (index === null) return null;
  const total = doc.pages.length;
  const page = doc.pages[index];

  return (
    <Modal
      open
      onClose={onClose}
      size="xl"
      title={title}
      description={total > 1 ? t("student.page", { n: index + 1 }) + ` / ${total}` : page?.name}
      footer={
        <div className="flex w-full items-center justify-between gap-2">
          <div className="flex items-center gap-1">
            {total > 1 && (
              <>
                <IconButton label={t("pagination.prev")} disabled={index === 0} onClick={() => onIndex(index - 1)} className="disabled:opacity-40">
                  <ChevronLeft className="size-5" />
                </IconButton>
                <IconButton label={t("pagination.next")} disabled={index >= total - 1} onClick={() => onIndex(index + 1)} className="disabled:opacity-40">
                  <ChevronRight className="size-5" />
                </IconButton>
              </>
            )}
          </div>
          <a href={fileUrl(studentId, kind, index, true)}>
            <Button variant="secondary" icon={<Download className="size-4" />}>
              {t("action.download")}
            </Button>
          </a>
        </div>
      }
    >
      <div className="flex min-h-[60vh] items-center justify-center rounded-lg bg-slate-100">
        {failed ? (
          <p className="text-sm text-slate-500">{t("err.generic")}</p>
        ) : !blob ? (
          <Spinner className="size-6" />
        ) : blob.type.startsWith("image/") ? (
          <img src={blob.url} alt={title} className="max-h-[70vh] w-auto rounded-md object-contain shadow-sm" />
        ) : blob.type === "application/pdf" ? (
          <iframe src={blob.url} title={title} className="h-[70vh] w-full rounded-md bg-white" />
        ) : (
          <div className="flex flex-col items-center gap-3 p-10 text-center">
            <FileText className="size-10 text-slate-400" />
            <p className="text-sm text-slate-500">{t("student.preview_failed")}</p>
          </div>
        )}
      </div>
    </Modal>
  );
}
