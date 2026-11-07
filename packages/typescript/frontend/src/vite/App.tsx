import { BrowserRouter, Route, Routes } from 'react-router-dom';
import { AppProviders } from './AppProviders';
import { AuthCompletePage } from './pages/AuthComplete';
import { DashboardPage } from './pages/Dashboard';
import { HomePage } from './pages/Home';
import { OrgPlaceholderPage } from './pages/OrgPlaceholder';
import { SignInPage } from './pages/SignIn';

export function App() {
  return (
    <AppProviders>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/dashboard" element={<DashboardPage />} />
          <Route path="/auth/signin" element={<SignInPage />} />
          <Route path="/auth/complete" element={<AuthCompletePage />} />
          <Route path="/orgs/:organizationId/*" element={<OrgPlaceholderPage />} />
        </Routes>
      </BrowserRouter>
    </AppProviders>
  );
}
