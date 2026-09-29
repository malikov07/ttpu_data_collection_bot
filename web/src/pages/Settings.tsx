import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Bot, ShieldCheck } from "lucide-react";
import { useEffect, useState } from "react";
import { useToast } from "../components/overlay";
import { Button, Card, CardHeader, Field, Input, PageHeader, PageLoader, Switch } from "../components/ui";
import { useI18n } from "../i18n";
import { api } from "../lib/api";
import { errorMessage } from "../lib/auth";
import type { Prefs, SettingsPayload } from "../lib/types";

function ToggleRow({ title, hint, checked, onChange }: { title: string; hint: string; checked: boolean; onChange: (v: boolean) => void }) {
  return (
    <div className="flex items-start justify-between gap-6 px-5 py-4">
      <div>
        <p className="text-sm font-medium text-slate-900">{title}</p>
        <p className="mt-0.5 text-[13px] text-slate-500">{hint}</p>
      </div>
      <Switch checked={checked} onChange={onChange} label={title} />
    </div>
  );
}

function PrefsCard({ initial }: { initial: Prefs }) {
  const { t } = useI18n();
  const toast = useToast();
  const qc = useQueryClient();
  const [prefs, setPrefs] = useState(initial);
  useEffect(() => setPrefs(initial), [initial]);
  const dirty = JSON.stringify(prefs) !== JSON.stringify(initial);

  const save = useMutation({
    mutationFn: (next: Prefs) => api.put<SettingsPayload>("/api/settings", next),
    onSuccess: (data) => {
      qc.setQueryData(["settings"], data);
      toast.success(t("settings.saved"));
    },
    onError: (err) => toast.error(errorMessage(err, t)),
  });
  const set = <K extends keyof Prefs>(key: K, value: Prefs[K]) => setPrefs((p) => ({ ...p, [key]: value }));
  const num = (key: "max_document_pages" | "min_student_age" | "max_student_age") => (id: string) => (
    <Input id={id} type="number" inputMode="numeric" value={prefs[key]} onChange={(e) => set(key, Number(e.target.value))} />
  );

  return (
    <Card>
      <CardHeader title={t("settings.bot")} icon={<Bot className="size-[18px]" />} />
      <div className="divide-y divide-slate-100">
        <ToggleRow
          title={t("settings.registration_open")}
          hint={t("settings.registration_open_hint")}
          checked={prefs.registration_open}
          onChange={(v) => set("registration_open", v)}
        />
        <ToggleRow
          title={t("settings.notify_leaders")}
          hint={t("settings.notify_leaders_hint")}
          checked={prefs.notify_leaders}
          onChange={(v) => set("notify_leaders", v)}
        />
        <div className="grid gap-5 px-5 py-5 sm:grid-cols-3">
          <Field label={t("settings.min_age")}>{num("min_student_age")}</Field>
          <Field label={t("settings.max_age")}>{num("max_student_age")}</Field>
          <Field label={t("settings.max_pages")}>{num("max_document_pages")}</Field>
        </div>
      </div>
      <div className="flex justify-end gap-2 border-t border-slate-100 bg-slate-50/60 px-5 py-3">
        <Button variant="secondary" disabled={!dirty} onClick={() => setPrefs(initial)}>
          {t("action.cancel")}
        </Button>
        <Button disabled={!dirty} loading={save.isPending} onClick={() => save.mutate(prefs)}>
          {t("action.save")}
        </Button>
      </div>
    </Card>
  );
}

export function SettingsPage() {
  const { t } = useI18n();
  const { data } = useQuery({ queryKey: ["settings"], queryFn: () => api.get<SettingsPayload>("/api/settings") });
  if (!data) return <PageLoader />;
  return (
    <>
      <PageHeader title={t("settings.title")} />
      <div className="grid gap-6 xl:grid-cols-[2fr_1fr]">
        <PrefsCard initial={data.prefs} />
        <Card className="h-fit">
          <CardHeader title={t("settings.privacy")} icon={<ShieldCheck className="size-[18px]" />} />
          <p className="px-5 py-4 text-sm leading-relaxed text-slate-600">{t("settings.privacy_body")}</p>
        </Card>
      </div>
    </>
  );
}
