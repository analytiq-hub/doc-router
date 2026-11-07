import { useEffect, useMemo } from 'react';
import { useAppSession } from '@/contexts/AppSessionContext';
import { DocRouterAccountApi } from '@/utils/api';
import type { AppSession } from '@/types/AppSession';
import { toast } from 'react-toastify';
import { toastActionError } from '@/utils/toastActionError';

/**
 * After auth, send the user to their first org dashboard or org settings.
 * `navigate` accepts SPA router paths (Next or React Router).
 */
export function useDashboardRedirect(navigate: (path: string) => void) {
  const { session, status } = useAppSession();
  const docRouterAccountApi = useMemo(() => new DocRouterAccountApi(), []);

  useEffect(() => {
    const redirectToDashboard = async () => {
      if (status === 'authenticated') {
        try {
          const appSession = session as AppSession | null;
          if (!appSession?.user?.id) {
            console.warn('No user ID found in session');
            return;
          }

          const response = await docRouterAccountApi.listOrganizations({ userId: appSession.user.id });
          const { organizations } = response;

          if (organizations && organizations.length > 0) {
            navigate(`/orgs/${organizations[0].id}/dashboard`);
          } else {
            toast.error('No organizations found');
            navigate('/settings/organizations');
          }
        } catch (error) {
          console.error('Error fetching organizations:', error);
          toastActionError('Failed to fetch organizations', error);
          navigate('/settings/organizations');
        }
      } else if (status === 'unauthenticated') {
        navigate('/auth/signin');
      }
    };

    void redirectToDashboard();
  }, [navigate, status, session, docRouterAccountApi]);
}
