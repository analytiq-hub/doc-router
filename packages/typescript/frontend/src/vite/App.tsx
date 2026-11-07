import { BrowserRouter, Route, Routes } from 'react-router-dom';
import { AppSessionProvider } from '@/contexts/AppSessionContext';
import { ThemeShell } from './ThemeShell';
import { AuthCompletePage } from './pages/AuthComplete';
import { HomePage } from './pages/Home';
import { SignInPage } from './pages/SignIn';

export function App() {
  return (
    <ThemeShell>
      <AppSessionProvider initialSession={null}>
        <BrowserRouter>
          <Routes>
            <Route path="/" element={<HomePage />} />
            <Route path="/auth/signin" element={<SignInPage />} />
            <Route path="/auth/complete" element={<AuthCompletePage />} />
          </Routes>
        </BrowserRouter>
      </AppSessionProvider>
    </ThemeShell>
  );
}
