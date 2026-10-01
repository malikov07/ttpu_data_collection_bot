import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Compass } from "lucide-react";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Link, Route, Routes } from "react-router-dom";
import { Layout } from "./components/Layout";
import { ToastProvider } from "./components/overlay";
import { Button, Card, EmptyState } from "./components/ui";
import { I18nProvider, useI18n } from "./i18n";
import "./index.css";
import { ApiError } from "./lib/api";
import { RequireAuth } from "./lib/auth";
import { ActivityPage } from "./pages/Activity";
import { CertificatesPage } from "./pages/Certificates";
import { DashboardPage } from "./pages/Dashboard";
import { GroupsPage } from "./pages/Groups";
import { LoginPage } from "./pages/Login";
import { AccountsPage } from "./pages/Accounts";
import { ChangePasswordPage } from "./pages/ChangePassword";
import { SettingsPage } from "./pages/Settings";
import { StudentDetailPage } from "./pages/StudentDetail";
import { StudentsPage } from "./pages/Students";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 15_000,
      refetchOnWindowFocus: true,
      retry: (count, err) => !(err instanceof ApiError && err.status < 500) && count < 2,
    },
  },
});

// A session that expires while the app is open sends the user back to sign in.
queryClient.getQueryCache().subscribe((event) => {
  const err = event.query.state.error;
  if (event.type === "updated" && err instanceof ApiError && err.status === 401 && event.query.queryKey[0] !== "me") {
    queryClient.invalidateQueries({ queryKey: ["me"] });
  }
});

function NotFound() {
  const { t } = useI18n();
  return (
    <Card>
      <EmptyState
        icon={<Compass className="size-6" />}
        title={t("notfound.title")}
        action={
          <Link to="/">
            <Button variant="secondary">{t("notfound.back")}</Button>
          </Link>
        }
      />
    </Card>
  );
}

function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route
        element={
          <RequireAuth>
            <Layout />
          </RequireAuth>
        }
      >
        <Route index element={<DashboardPage />} />
        <Route path="students" element={<StudentsPage />} />
        <Route path="students/:id" element={<StudentDetailPage />} />
        <Route path="certificates" element={<CertificatesPage />} />
        <Route path="groups" element={<GroupsPage />} />
        <Route path="password" element={<ChangePasswordPage />} />
        <Route path="accounts" element={<RequireAuth admin><AccountsPage /></RequireAuth>} />
        <Route path="activity" element={<RequireAuth admin><ActivityPage /></RequireAuth>} />
        <Route path="settings" element={<RequireAuth admin><SettingsPage /></RequireAuth>} />
        <Route path="*" element={<NotFound />} />
      </Route>
    </Routes>
  );
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <I18nProvider>
        <ToastProvider>
          <BrowserRouter>
            <App />
          </BrowserRouter>
        </ToastProvider>
      </I18nProvider>
    </QueryClientProvider>
  </StrictMode>,
);
