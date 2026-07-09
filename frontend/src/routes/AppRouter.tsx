import type { ReactElement } from "react";
import { Navigate, Route, Routes } from "react-router-dom";

import { AppLayout } from "../layouts/AppLayout";
import { AssistantPage } from "../pages/AssistantPage";
import { DashboardPage } from "../pages/DashboardPage";
import { LoginPage } from "../pages/LoginPage";
import { ProjectDetailPage } from "../pages/ProjectDetailPage";
import { ProjectsPage } from "../pages/ProjectsPage";
import { RegisterPage } from "../pages/RegisterPage";
import { ReportsPage } from "../pages/ReportsPage";
import { SettingsPage } from "../pages/SettingsPage";

function ProtectedRoute({ children }: { children: ReactElement }) {
  const token = localStorage.getItem("vision_capital_ai_token");
  if (!token) {
    return <Navigate to="/login" replace />;
  }
  return children;
}

export function AppRouter() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />
      <Route
        path="*"
        element={
          <ProtectedRoute>
            <AppLayout>
              <Routes>
                <Route path="/" element={<DashboardPage />} />
                <Route path="/projects" element={<ProjectsPage />} />
                <Route path="/projects/:projectId" element={<ProjectDetailPage />} />
                <Route path="/assistant" element={<AssistantPage />} />
                <Route path="/reports" element={<ReportsPage />} />
                <Route path="/settings" element={<SettingsPage />} />
              </Routes>
            </AppLayout>
          </ProtectedRoute>
        }
      />
    </Routes>
  );
}
