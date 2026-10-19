export interface AppSession {
  user: {
    id: string;
    email: string;
    name?: string | null;
    isSysadmin: boolean;
  };
  providerAccessToken?: string;
  apiAccessToken: string;
  expires: string;
}
