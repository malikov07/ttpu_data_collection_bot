import clsx from "clsx";
import { AlertTriangle, CheckCircle2, X, XCircle } from "lucide-react";
import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { useI18n } from "../i18n";
import { Button, IconButton } from "./ui";

// ------------------------------------------------------------------ Modal

export function Modal({
  open,
  onClose,
  title,
  description,
  children,
  footer,
  size = "md",
}: {
  open: boolean;
  onClose: () => void;
  title: ReactNode;
  description?: ReactNode;
  children?: ReactNode;
  footer?: ReactNode;
  size?: "sm" | "md" | "lg" | "xl";
}) {
  const { t } = useI18n();
  const panel = useRef<HTMLDivElement>(null);
  // Parents often pass a new onClose on every render (e.g. on each keystroke);
  // keep it in a ref so the effect below runs only when the modal opens, not
  // again on every render, which would pull focus back to the first field.
  const onCloseRef = useRef(onClose);
  useEffect(() => {
    onCloseRef.current = onClose;
  });

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onCloseRef.current();
    document.addEventListener("keydown", onKey);
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const focusable = panel.current?.querySelector<HTMLElement>("input, textarea, select, button:not([data-close])");
    focusable?.focus();
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = prevOverflow;
    };
  }, [open]);

  if (!open) return null;
  const width = { sm: "max-w-md", md: "max-w-lg", lg: "max-w-2xl", xl: "max-w-5xl" }[size];
  return createPortal(
    <div className="fixed inset-0 z-50 flex items-end justify-center p-0 sm:items-center sm:p-6" role="dialog" aria-modal="true">
      <div className="animate-fade-in absolute inset-0 bg-slate-900/40 backdrop-blur-[2px]" onClick={onClose} />
      <div
        ref={panel}
        className={clsx(
          "animate-pop-in relative flex max-h-[92vh] w-full flex-col rounded-t-2xl bg-white shadow-pop sm:rounded-2xl",
          width,
        )}
      >
        <div className="flex items-start justify-between gap-4 px-6 pt-5 pb-4">
          <div className="min-w-0">
            <h2 className="text-lg font-semibold text-slate-900">{title}</h2>
            {description && <div className="mt-1 text-sm text-slate-500">{description}</div>}
          </div>
          <IconButton label={t("action.close")} onClick={onClose} data-close className="-mt-1 -mr-2">
            <X className="size-5" />
          </IconButton>
        </div>
        {children && <div className="min-h-0 flex-1 overflow-y-auto px-6 pb-5">{children}</div>}
        {footer && <div className="flex justify-end gap-2 rounded-b-2xl border-t border-slate-100 bg-slate-50/70 px-6 py-3.5">{footer}</div>}
      </div>
    </div>,
    document.body,
  );
}

export function ConfirmDialog({
  open,
  onClose,
  onConfirm,
  title,
  body,
  confirmLabel,
  loading,
}: {
  open: boolean;
  onClose: () => void;
  onConfirm: () => void;
  title: ReactNode;
  body: ReactNode;
  confirmLabel: string;
  loading?: boolean;
}) {
  const { t } = useI18n();
  return (
    <Modal
      open={open}
      onClose={onClose}
      size="sm"
      title={
        <span className="flex items-center gap-2">
          <AlertTriangle className="size-5 text-red-500" />
          {title}
        </span>
      }
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            {t("action.cancel")}
          </Button>
          <Button variant="danger" loading={loading} onClick={onConfirm}>
            {confirmLabel}
          </Button>
        </>
      }
    >
      <p className="text-sm leading-relaxed text-slate-600">{body}</p>
    </Modal>
  );
}

// ------------------------------------------------------------------ Toasts

interface Toast {
  id: number;
  kind: "success" | "error";
  text: string;
}

const ToastContext = createContext<(kind: Toast["kind"], text: string) => void>(() => {});

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const push = useCallback((kind: Toast["kind"], text: string) => {
    const id = Date.now() + Math.random();
    setToasts((all) => [...all.slice(-3), { id, kind, text }]);
    setTimeout(() => setToasts((all) => all.filter((x) => x.id !== id)), kind === "error" ? 6000 : 3500);
  }, []);

  return (
    <ToastContext.Provider value={push}>
      {children}
      {createPortal(
        <div className="pointer-events-none fixed inset-x-0 bottom-0 z-[60] flex flex-col items-center gap-2 p-4 sm:items-end sm:p-6">
          {toasts.map((toast) => (
            <div
              key={toast.id}
              role="status"
              className="animate-pop-in pointer-events-auto flex w-full max-w-sm items-start gap-3 rounded-xl bg-white px-4 py-3 shadow-pop ring-1 ring-slate-200"
            >
              {toast.kind === "success" ? (
                <CheckCircle2 className="mt-0.5 size-5 shrink-0 text-emerald-500" />
              ) : (
                <XCircle className="mt-0.5 size-5 shrink-0 text-red-500" />
              )}
              <p className="text-sm text-slate-700">{toast.text}</p>
            </div>
          ))}
        </div>,
        document.body,
      )}
    </ToastContext.Provider>
  );
}

export function useToast() {
  const push = useContext(ToastContext);
  return {
    success: (text: string) => push("success", text),
    error: (text: string) => push("error", text),
  };
}

// ------------------------------------------------------------------ Dropdown menu

export interface MenuItem {
  label: string;
  icon?: ReactNode;
  onSelect: () => void;
  danger?: boolean;
}

export function Menu({ trigger, items, label }: { trigger: ReactNode; items: MenuItem[]; label: string }) {
  const [open, setOpen] = useState(false);
  const root = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => !root.current?.contains(e.target as Node) && setOpen(false);
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  return (
    <div ref={root} className="relative">
      <button
        type="button"
        aria-label={label}
        title={label}
        aria-haspopup="menu"
        aria-expanded={open}
        onClick={() => setOpen((o) => !o)}
        className="inline-flex size-8 items-center justify-center rounded-lg text-slate-500 hover:bg-slate-100 hover:text-slate-900"
      >
        {trigger}
      </button>
      {open && (
        <div role="menu" className="animate-pop-in absolute right-0 z-30 mt-1 w-56 rounded-xl bg-white p-1 shadow-pop ring-1 ring-slate-200">
          {items.map((item) => (
            <button
              key={item.label}
              type="button"
              role="menuitem"
              onClick={() => {
                setOpen(false);
                item.onSelect();
              }}
              className={clsx(
                "flex w-full items-center gap-2.5 rounded-lg px-3 py-2 text-left text-sm",
                item.danger ? "text-red-600 hover:bg-red-50" : "text-slate-700 hover:bg-slate-100",
              )}
            >
              {item.icon}
              {item.label}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
