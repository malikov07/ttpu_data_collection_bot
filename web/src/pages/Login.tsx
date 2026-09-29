import { useQueryClient } from "@tanstack/react-query";
import { GraduationCap, Lock, LogIn } from "lucide-react";
import { useState, type FormEvent } from "react";
import { Navigate, useLocation, useNavigate } from "react-router-dom";
import { Button, ErrorBanner, Field, Input } from "../components/ui";
import { LANGS, useI18n } from "../i18n";
import { api, ApiError } from "../lib/api";
import { useMe } from "../lib/auth";

export function LoginPage() {
  const { t, lang, setLang } = useI18n();
  const me = useMe();
  const qc = useQueryClient();
  const navigate = useNavigate();
  const location = useLocation();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const from = (location.state as { from?: string } | null)?.from || "/";

  if (me.data) return <Navigate to={me.data.must_change_password ? "/password" : from} replace />;

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api.post("/api/auth/login", { username, password });
      await qc.invalidateQueries({ queryKey: ["me"] });
      navigate(from, { replace: true });
    } catch (err) {
      setError(err instanceof ApiError && err.status === 429 ? t("login.too_many") : t("login.failed"));
      setPassword("");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="grid min-h-screen lg:grid-cols-[1.1fr_1fr]">
      <section className="relative hidden overflow-hidden bg-brand-900 p-12 text-white lg:flex lg:flex-col lg:justify-between">
        <div aria-hidden className="absolute -top-40 -right-40 size-[36rem] rounded-full bg-brand-600/30 blur-3xl" />
        <div aria-hidden className="absolute -bottom-48 -left-24 size-[28rem] rounded-full bg-sky-400/10 blur-3xl" />
        <div className="relative flex items-center gap-3">
          <div className="flex size-11 items-center justify-center rounded-xl bg-white/10 ring-1 ring-white/20">
            <GraduationCap className="size-6" />
          </div>
          <span className="text-lg font-semibold">{t("app.name")}</span>
        </div>
        <div className="relative max-w-md">
          <h2 className="text-4xl leading-tight font-semibold tracking-tight">{t("app.tagline")}</h2>
          <p className="mt-4 text-brand-100">{t("login.footer")}</p>
        </div>
        <p className="relative text-sm text-brand-300">© {new Date().getFullYear()} TTPU</p>
      </section>

      <section className="flex flex-col bg-white">
        <div className="flex justify-end gap-1 p-6">
          {LANGS.map((l) => (
            <button
              key={l.code}
              type="button"
              onClick={() => setLang(l.code)}
              className={
                lang === l.code
                  ? "rounded-md bg-slate-100 px-2.5 py-1 text-xs font-semibold text-slate-900"
                  : "rounded-md px-2.5 py-1 text-xs font-medium text-slate-500 hover:text-slate-900"
              }
            >
              {l.label}
            </button>
          ))}
        </div>
        <div className="flex flex-1 items-center justify-center px-6 pb-16">
          <form onSubmit={submit} className="w-full max-w-sm">
            <div className="mb-8 flex size-12 items-center justify-center rounded-2xl bg-brand-50 text-brand-700 lg:hidden">
              <GraduationCap className="size-6" />
            </div>
            <h1 className="text-2xl font-semibold tracking-tight text-slate-900">{t("login.title")}</h1>
            <p className="mt-2 text-sm text-slate-500">{t("login.subtitle")}</p>

            <div className="mt-8 space-y-5">
              {error && <ErrorBanner>{error}</ErrorBanner>}
              <Field label={t("login.username")}>
                {(id) => (
                  <Input
                    id={id}
                    required
                    autoFocus
                    autoComplete="username"
                    autoCapitalize="none"
                    spellCheck={false}
                    value={username}
                    onChange={(e) => setUsername(e.target.value)}
                  />
                )}
              </Field>
              <Field label={t("login.password")}>
                {(id) => (
                  <Input id={id} type="password" required autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} />
                )}
              </Field>
              <Button type="submit" className="w-full" loading={busy} icon={<LogIn className="size-4" />}>
                {t("login.submit")}
              </Button>
            </div>

            <p className="mt-10 flex items-center gap-2 text-xs text-slate-400">
              <Lock className="size-3.5" />
              {t("login.footer")}
            </p>
          </form>
        </div>
      </section>
    </div>
  );
}
