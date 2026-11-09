import { Routes, Route } from "react-router-dom";
import RequireAuth from "./components/auth/RequireAuth";
import AccountPage from "./pages/AccountPage";
import AnalysisDetailPage from "./pages/AnalysisDetailPage";
import AnalyticsPage from "./pages/AnalyticsPage";
import HistoryPage from "./pages/HistoryPage";
import LandingPage from "./pages/LandingPage";
import LoginPage from "./pages/LoginPage";
import RegisterPage from "./pages/RegisterPage";
import WorkspacePage from "./pages/WorkspacePage";

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<LandingPage />} />
      <Route path="/workspace" element={<WorkspacePage />} />
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />

      {/* signed-in users only */}
      <Route element={<RequireAuth />}>
        <Route path="/history" element={<HistoryPage />} />
        <Route path="/history/:id" element={<AnalysisDetailPage />} />
        <Route path="/analytics" element={<AnalyticsPage />} />
        <Route path="/account" element={<AccountPage />} />
      </Route>
    </Routes>
  );
}