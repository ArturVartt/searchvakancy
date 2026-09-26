import { BrowserRouter, Route, Routes } from "react-router-dom";
import { Layout } from "./components/Layout";
import { RequireAuth } from "./components/RequireAuth";
import { AuthProvider } from "./lib/AuthContext";
import { JobsPage } from "./pages/JobsPage";
import { FavoritesPage } from "./pages/FavoritesPage";
import { NotificationsPage } from "./pages/NotificationsPage";
import { LoginPage } from "./pages/LoginPage";
import { ApplicationsPage } from "./pages/ApplicationsPage";
import { ProfileSetsPage } from "./pages/ProfileSetsPage";
import { ProfileSetFormPage } from "./pages/ProfileSetFormPage";

export function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route element={<Layout />}>
            <Route index element={<JobsPage />} />
            <Route path="login" element={<LoginPage />} />
            <Route
              path="favorites"
              element={
                <RequireAuth>
                  <FavoritesPage />
                </RequireAuth>
              }
            />
            <Route
              path="notifications"
              element={
                <RequireAuth>
                  <NotificationsPage />
                </RequireAuth>
              }
            />
            <Route
              path="applications"
              element={
                <RequireAuth>
                  <ApplicationsPage />
                </RequireAuth>
              }
            />
            <Route
              path="profile-sets"
              element={
                <RequireAuth>
                  <ProfileSetsPage />
                </RequireAuth>
              }
            />
            <Route
              path="profile-sets/new"
              element={
                <RequireAuth>
                  <ProfileSetFormPage />
                </RequireAuth>
              }
            />
            <Route
              path="profile-sets/:id/edit"
              element={
                <RequireAuth>
                  <ProfileSetFormPage />
                </RequireAuth>
              }
            />
          </Route>
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}
