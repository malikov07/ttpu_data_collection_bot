import clsx from "clsx";
import { CheckCircle2, CircleDashed } from "lucide-react";
import { useState } from "react";
import { useI18n } from "../i18n";
import { initials } from "../lib/format";
import type { DocKind, Student } from "../lib/types";

/** The student's 3x4 photo (served by our API), or initials as a fallback. */
export function StudentAvatar({ student, size = "md" }: { student: Pick<Student, "id" | "full_name" | "documents" | "updated_at">; size?: "sm" | "md" | "xl" }) {
  const [failed, setFailed] = useState(false);
  const cls = { sm: "size-9 text-xs", md: "size-11 text-sm", xl: "h-32 w-24 text-2xl" }[size];
  const shape = size === "xl" ? "rounded-xl" : "rounded-full";
  if (student.documents.photo.present && !failed) {
    return (
      <img
        src={`/api/students/${student.id}/documents/photo/0?v=${encodeURIComponent(student.updated_at)}`}
        alt=""
        loading="lazy"
        onError={() => setFailed(true)}
        className={clsx(cls, shape, "shrink-0 bg-slate-100 object-cover ring-1 ring-slate-200")}
      />
    );
  }
  return (
    <span className={clsx(cls, shape, "inline-flex shrink-0 items-center justify-center bg-brand-100 font-semibold text-brand-800")}>
      {initials(student.full_name)}
    </span>
  );
}

export function DocPill({ kind, present }: { kind: DocKind; present: boolean }) {
  const { t } = useI18n();
  return (
    <span
      title={`${t(`doc.${kind}`)}: ${present ? t("doc.present") : t("doc.missing")}`}
      className={clsx(
        "inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 text-[11px] font-medium ring-1 ring-inset",
        present ? "bg-emerald-50 text-emerald-700 ring-emerald-600/15" : "bg-amber-50 text-amber-800 ring-amber-600/20",
      )}
    >
      {present ? <CheckCircle2 className="size-3" /> : <CircleDashed className="size-3" />}
      {t(`doc.${kind}`)}
    </span>
  );
}

export function DocPills({ student }: { student: Student }) {
  return (
    <div className="flex flex-wrap gap-1.5">
      {(["passport", "photo", "cv"] as const).map((k) => (
        <DocPill key={k} kind={k} present={student.documents[k].present} />
      ))}
    </div>
  );
}
