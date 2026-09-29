import type { Translate } from "../i18n";

export function formatDate(iso: string | null | undefined, locale: string): string {
  if (!iso) return "—";
  // Dates without time ("2005-03-21") must not shift with the browser timezone.
  const date = iso.length === 10 ? new Date(`${iso}T12:00:00`) : new Date(iso);
  return date.toLocaleDateString(locale, { day: "2-digit", month: "2-digit", year: "numeric" });
}

export function formatDateTime(iso: string | null | undefined, locale: string): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleString(locale, {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function relativeTime(iso: string, t: Translate, locale: string): string {
  const diff = (Date.now() - new Date(iso).getTime()) / 1000;
  if (diff < 60) return t("time.just_now");
  if (diff < 3600) return t("time.minutes", { n: Math.floor(diff / 60) });
  if (diff < 86400) return t("time.hours", { n: Math.floor(diff / 3600) });
  if (diff < 7 * 86400) return t("time.days", { n: Math.floor(diff / 86400) });
  return formatDate(iso, locale);
}

/** +998901234567 → +998 90 123 45 67 */
export function formatPhone(phone: string): string {
  if (phone.startsWith("+998") && phone.length === 13) {
    const d = phone.slice(4);
    return `+998 ${d.slice(0, 2)} ${d.slice(2, 5)} ${d.slice(5, 7)} ${d.slice(7)}`;
  }
  return phone;
}

export function initials(name: string): string {
  const parts = name.replace(/@.*/, "").split(/[\s._-]+/).filter(Boolean);
  return ((parts[0]?.[0] ?? "") + (parts[1]?.[0] ?? "")).toUpperCase() || "?";
}

export function actorLabel(actor: string, t: Translate): string {
  return actor.startsWith("tg:") ? t("activity.bot_user", { id: actor.slice(3) }) : actor;
}
