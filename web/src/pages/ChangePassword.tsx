import { useMutation, useQueryClient } from "@tanstack/react-query";
import { KeyRound } from "lucide-react";
import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { useToast } from "../components/overlay";
import { Button, Card, CardHeader, Field, Input, PageHeader } from "../components/ui";
import { useI18n } from "../i18n";
import { api, ApiError } from "../lib/api";
import { errorMessage, useUser } from "../lib/auth";

export function ChangePasswordPage() {
  const { t } = useI18n();
  const user = useUser();
  const toast = useToast();
  const qc = useQueryClient();
  const navigate = useNavigate();
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [repeat, setRepeat] = useState("");
  const [error, setError] = useState<{ field?: string; message: string } | null>(null);

  const save = useMutation({
    mutationFn: () => api.post("/api/auth/password", { current_password: current, new_password: next }),
    onSuccess: async () => {
      toast.success(t("password.changed"));
      await qc.invalidateQueries({ queryKey: ["me"] });
      navigate("/", { replace: true });
    },
    onError: (err) => setError({ field: err instanceof ApiError ? err.field : undefined, message: errorMessage(err, t) }),
  });

  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (next !== repeat) {
      setError({ field: "repeat", message: t("password.mismatch") });
      return;
    }
    setError(null);
    save.mutate();
  };
  const err = (f: string) => (error?.field === f ? error.message : null);

  return (
    <>
      <PageHeader title={t("password.title")} />
      <Card className="max-w-lg">
        <CardHeader
          title={user.username}
          subtitle={user.must_change_password ? t("password.forced") : undefined}
          icon={<KeyRound className="size-[18px]" />}
        />
        <form onSubmit={submit} className="space-y-5 p-5">
          <Field label={t("password.current")} error={err("current_password")}>
            {(id) => <Input id={id} type="password" required autoComplete="current-password" value={current} onChange={(e) => setCurrent(e.target.value)} invalid={!!err("current_password")} />}
          </Field>
          <Field label={t("password.new")} hint={t("password.hint")} error={err("new_password")}>
            {(id) => <Input id={id} type="password" required minLength={8} autoComplete="new-password" value={next} onChange={(e) => setNext(e.target.value)} invalid={!!err("new_password")} />}
          </Field>
          <Field label={t("password.repeat")} error={err("repeat")}>
            {(id) => <Input id={id} type="password" required autoComplete="new-password" value={repeat} onChange={(e) => setRepeat(e.target.value)} invalid={!!err("repeat")} />}
          </Field>
          {error && !error.field && <p className="text-sm text-red-600">{error.message}</p>}
          <div className="flex justify-end">
            <Button type="submit" loading={save.isPending}>
              {t("action.save")}
            </Button>
          </div>
        </form>
      </Card>
    </>
  );
}
