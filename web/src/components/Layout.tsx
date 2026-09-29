import clsx from "clsx";
import {
  Activity,
  GraduationCap,
  KeyRound,
  LayoutDashboard,
  LogOut,
  Menu,
  Settings,
  ShieldCheck,
  UsersRound,
  X,
  type LucideIcon,
} from "lucide-react";
import { useEffect, useState } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";
import { LANGS, useI18n, type MessageKey } from "../i18n";
import { useLogout, useUser } from "../lib/auth";
import { Avatar, IconButton } from "./ui";

interface NavItem {
  to: string;
  label: MessageKey;
  icon: LucideIcon;
}

const MAIN: NavItem[] = [
  { to: "/", label: "nav.dashboard", icon: LayoutDashboard },
  { to: "/students", label: "nav.students", icon: GraduationCap },
  { to: "/groups", label: "nav.groups", icon: UsersRound },
];
const ADMIN: NavItem[] = [
  { to: "/accounts", label: "nav.accounts", icon: ShieldCheck },
  { to: "/activity", label: "nav.activity", icon: Activity },
  { to: "/settings", label: "nav.settings", icon: Settings },
];

function Logo() {
  const { t } = useI18n();
  return (
    <div className="flex items-center gap-3 px-2">
      <div className="flex size-9 items-center justify-center rounded-xl bg-white/10 ring-1 ring-white/20">
        <GraduationCap className="size-5 text-white" />
      </div>
      <div className="min-w-0 leading-tight">
        <p className="line-clamp-2 text-sm font-semibold text-white">{t("app.name")}</p>
        <p className="truncate text-[11px] text-brand-200">TTPU</p>
      </div>
    </div>
  );
}

function NavGroup({ items, onNavigate }: { items: NavItem[]; onNavigate?: () => void }) {
  const { t } = useI18n();
  return (
    <ul className="space-y-0.5">
      {items.map(({ to, label, icon: Icon }) => (
        <li key={to}>
          <NavLink
            to={to}
            end={to === "/"}
            onClick={onNavigate}
            className={({ isActive }) =>
              clsx(
                "group flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
                isActive ? "bg-white/12 text-white" : "text-brand-100 hover:bg-white/6 hover:text-white",
              )
            }
          >
            <Icon className="size-[18px] shrink-0 opacity-90" />
            {t(label)}
          </NavLink>
        </li>
      ))}
    </ul>
  );
}

function Sidebar({ onNavigate }: { onNavigate?: () => void }) {
  const { t, lang, setLang } = useI18n();
  const user = useUser();
  const logout = useLogout();
  return (
    <div className="flex h-full flex-col bg-brand-900 px-3 py-5">
      <Logo />
      <nav className="mt-8 flex-1 space-y-6 overflow-y-auto">
        <NavGroup items={MAIN} onNavigate={onNavigate} />
        {user.is_admin && (
          <div>
            <p className="mb-2 px-3 text-[11px] font-semibold tracking-wider text-brand-300 uppercase">
              {t("nav.section_admin")}
            </p>
            <NavGroup items={ADMIN} onNavigate={onNavigate} />
          </div>
        )}
      </nav>

      <div className="mt-4 space-y-3 border-t border-white/10 pt-4">
        <div className="flex rounded-lg bg-white/5 p-0.5" role="group" aria-label={t("menu.language")}>
          {LANGS.map((l) => (
            <button
              key={l.code}
              type="button"
              onClick={() => setLang(l.code)}
              className={clsx(
                "flex-1 rounded-md py-1 text-xs font-medium transition-colors",
                lang === l.code ? "bg-white text-brand-900 shadow-sm" : "text-brand-100 hover:text-white",
              )}
            >
              {l.code.toUpperCase()}
            </button>
          ))}
        </div>
        <div className="flex items-center gap-3 rounded-lg px-2 py-1.5">
          <Avatar name={user.name || user.username} size="sm" />
          <div className="min-w-0 flex-1 leading-tight">
            <p className="truncate text-[13px] font-medium text-white">{user.name || user.username}</p>
            <p className="truncate text-[11px] text-brand-200">{t(`role.${user.role}`)} · {user.username}</p>
          </div>
          <NavLink
            to="/password"
            onClick={onNavigate}
            title={t("nav.password")}
            aria-label={t("nav.password")}
            className="inline-flex size-9 items-center justify-center rounded-lg text-brand-200 hover:bg-white/10 hover:text-white"
          >
            <KeyRound className="size-4" />
          </NavLink>
          <IconButton label={t("action.sign_out")} onClick={logout} className="text-brand-200 hover:bg-white/10 hover:text-white">
            <LogOut className="size-4" />
          </IconButton>
        </div>
        <p className="px-2 text-[10px] text-brand-300/70">{t("app.credit")}</p>
      </div>
    </div>
  );
}

export function Layout() {
  const [open, setOpen] = useState(false);
  const location = useLocation();
  const { t } = useI18n();
  useEffect(() => setOpen(false), [location.pathname]);

  return (
    <div className="min-h-screen">
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-64 lg:block">
        <Sidebar />
      </aside>

      {open && (
        <div className="fixed inset-0 z-40 lg:hidden">
          <div className="animate-fade-in absolute inset-0 bg-slate-900/50" onClick={() => setOpen(false)} />
          <div className="animate-slide-in absolute inset-y-0 left-0 w-72">
            <Sidebar onNavigate={() => setOpen(false)} />
          </div>
          <IconButton label={t("action.close")} onClick={() => setOpen(false)} className="absolute top-4 left-[19rem] text-white hover:bg-white/10">
            <X className="size-5" />
          </IconButton>
        </div>
      )}

      <div className="lg:pl-64">
        <header className="sticky top-0 z-20 flex h-14 items-center gap-3 border-b border-slate-200 bg-white/90 px-4 backdrop-blur lg:hidden">
          <IconButton label="Menu" onClick={() => setOpen(true)}>
            <Menu className="size-5" />
          </IconButton>
          <span className="text-sm font-semibold">{t("app.name")}</span>
        </header>
        <main className="mx-auto w-full max-w-7xl px-4 py-6 sm:px-6 lg:px-10 lg:py-10">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
