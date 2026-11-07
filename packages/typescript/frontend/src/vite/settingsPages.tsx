import SettingsPage from '@/pages/settings/index';
import OrganizationsSettingsPage from '@/pages/settings/organizations';
import OrganizationEditSettingsPage from '@/pages/settings/organization-edit';
import OrganizationWebhooksPage from '@/pages/settings/organization-webhooks';
import OrganizationSubscriptionPage from '@/pages/settings/organization-subscription';
import UserProfilePage from '@/pages/settings/user-profile';
import UserDeveloperPage from '@/pages/settings/user-developer';
import UserAccessTokensPage from '@/pages/settings/user-access-tokens';
import UserDeveloperAccountTokensPage from '@/pages/settings/developer-account-tokens';
import UserDeveloperOrgTokensPage from '@/pages/settings/developer-org-tokens';
import UserDeveloperOrgWebhooksPage from '@/pages/settings/developer-org-webhooks';
import AccountUsersPage from '@/pages/settings/account-users';
import AccountUserDetailPage from '@/pages/settings/account-user-detail';
import AccountLicensePage from '@/pages/settings/account-license';
import AccountDevelopmentPage from '@/pages/settings/account-development';
import DevelopmentAwsConfigPage from '@/pages/settings/development-aws-config';
import DevelopmentAwsCredentialsPage from '@/pages/settings/development-aws-credentials';
import DevelopmentAzureConfigPage from '@/pages/settings/development-azure-config';
import DevelopmentGcpConfigPage from '@/pages/settings/development-gcp-config';
import DevelopmentWorkerSettingsPage from '@/pages/settings/development-worker-settings';
import DevelopmentLlmManagerPage from '@/pages/settings/development-llm-manager';
import DevelopmentLlmManagerModelsPage from '@/pages/settings/development-llm-manager-models';
import DevelopmentLlmProviderPage from '@/pages/settings/development-llm-provider';

import { withRouteParams } from './withRouteParams';

export const SettingsIndex = SettingsPage;
export const SettingsOrganizations = OrganizationsSettingsPage;
export const SettingsOrganizationEdit = withRouteParams(
  ['organizationId'],
  OrganizationEditSettingsPage,
);
export const SettingsOrganizationWebhooks = OrganizationWebhooksPage;
export const SettingsOrganizationSubscription = OrganizationSubscriptionPage;
export const SettingsUserProfile = UserProfilePage;
export const SettingsUserDeveloper = UserDeveloperPage;
export const SettingsUserAccessTokens = UserAccessTokensPage;
export const SettingsDeveloperAccountTokens = UserDeveloperAccountTokensPage;
export const SettingsDeveloperOrgTokens = UserDeveloperOrgTokensPage;
export const SettingsDeveloperOrgWebhooks = UserDeveloperOrgWebhooksPage;
export const SettingsAccountUsers = AccountUsersPage;
export const SettingsAccountUserDetail = withRouteParams(['userId'], AccountUserDetailPage);
export const SettingsAccountLicense = AccountLicensePage;
export const SettingsAccountDevelopment = AccountDevelopmentPage;
export const SettingsDevelopmentAwsConfig = DevelopmentAwsConfigPage;
export const SettingsDevelopmentAwsCredentials = DevelopmentAwsCredentialsPage;
export const SettingsDevelopmentAzureConfig = DevelopmentAzureConfigPage;
export const SettingsDevelopmentGcpConfig = DevelopmentGcpConfigPage;
export const SettingsDevelopmentWorkerSettings = DevelopmentWorkerSettingsPage;
export const SettingsDevelopmentLlmManager = DevelopmentLlmManagerPage;
export const SettingsDevelopmentLlmManagerModels = DevelopmentLlmManagerModelsPage;
export const SettingsDevelopmentLlmProvider = DevelopmentLlmProviderPage;
