import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter as Router, Routes, Route, Navigate } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AppErrorBoundary } from "./components/layout/AppErrorBoundary";
import { useAuthStore } from "./stores/authStore";

// Pages
import Dashboard from "./pages/Dashboard";
import DevicesPage from "./pages/Devices";
import CompliancePage from "./pages/Compliance";
import SIEMPage from "./pages/SIEM";
import AlertsPage from "./pages/Alerts";
import UsersPage from "./pages/Users";
import AnalyticsPage from "./pages/Analytics";
import ThreatsPage from "./pages/Threats";
import LoginPage from "./pages/Login";
import RegisterPage from "./pages/Register";
import ForgotPasswordPage from "./pages/ForgotPassword";
import ResetPasswordPage from "./pages/ResetPassword";
import VerifyEmailPage from "./pages/VerifyEmail";
import CopilotPage from "./pages/Copilot";
import IncidentsPage from "./pages/Incidents";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime:  30_000,
      retry:      2,
      refetchOnWindowFocus: false,
    },
  },
});

function ProtectedRoute({
  children,
  permission,
}: {
  children: React.ReactNode;
  permission?: string;
}) {
  const user = useAuthStore((s) => s.user);
  const accessToken = useAuthStore((s) => s.accessToken);
  const fetchMe = useAuthStore((s) => s.fetchMe);

  React.useEffect(() => {
    if (!user && accessToken) {
      fetchMe().catch(() => undefined);
    }
  }, [user, accessToken, fetchMe]);

  if (!accessToken) {
    return <Navigate to="/login" replace />;
  }

  if (!permission || !user) {
    return <>{children}</>;
  }

  // Mirror backend has_permission(): ["*"] grants everything
  const hasPermission =
    user.permissions.includes("*") || user.permissions.includes(permission);

  if (hasPermission) {
    return <>{children}</>;
  }

  return <Navigate to="/" replace />;
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <AppErrorBoundary>
        <Router>
          <Routes>
            {/* Public auth routes */}
            <Route path="/login" element={<LoginPage />} />
            <Route path="/register" element={<RegisterPage />} />
            <Route path="/forgot-password" element={<ForgotPasswordPage />} />
            <Route path="/reset-password" element={<ResetPasswordPage />} />
            <Route path="/verify-email" element={<VerifyEmailPage />} />

            {/* Protected routes */}
            <Route path="/" element={<ProtectedRoute permission="monitoring:read"><Dashboard /></ProtectedRoute>} />
            <Route path="/devices" element={<ProtectedRoute permission="devices:read"><DevicesPage /></ProtectedRoute>} />
            <Route path="/compliance" element={<ProtectedRoute permission="compliance:read"><CompliancePage /></ProtectedRoute>} />
            <Route path="/siem" element={<ProtectedRoute permission="siem:read"><SIEMPage /></ProtectedRoute>} />
            <Route path="/alerts" element={<ProtectedRoute permission="compliance:read"><AlertsPage /></ProtectedRoute>} />
            <Route path="/incidents" element={<ProtectedRoute permission="incidents:read"><IncidentsPage /></ProtectedRoute>} />
            <Route path="/users" element={<ProtectedRoute permission="users:read"><UsersPage /></ProtectedRoute>} />
            <Route path="/analytics" element={<ProtectedRoute permission="reports:read"><AnalyticsPage /></ProtectedRoute>} />
            <Route path="/threats" element={<ProtectedRoute permission="threats:read"><ThreatsPage /></ProtectedRoute>} />
            <Route path="/copilot" element={<ProtectedRoute permission="ai:chat"><CopilotPage /></ProtectedRoute>} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </Router>
      </AppErrorBoundary>
    </QueryClientProvider>
  </React.StrictMode>
);
