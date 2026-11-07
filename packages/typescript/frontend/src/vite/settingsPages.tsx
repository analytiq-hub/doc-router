import SettingsPage from '@/app/settings/page';
import OrganizationsSettingsPage from '@/app/settings/organizations/page';
import OrganizationEditSettingsPage from '@/app/settings/organizations/[organizationId]/page';
import OrganizationWebhooksPage from '@/app/settings/organizations/[organizationId]/webhooks/page';
import OrganizationSubscriptionPage from '@/app/settings/organizations/[organizationId]/subscription/page';
import UserProfilePage from '@/app/settings/user/profile/page';
import UserDeveloperPage from '@/app/settings/user/developer/page';
import UserAccessTokensPage from '@/app/settings/user/access-tokens/page';
import UserDeveloperAccountTokensPage from '@/app/settings/user/developer/account-access-tokens/page';
import UserDeveloperOrgTokensPage from '@/app/settings/user/developer/organization-access-tokens/page';
import UserDeveloperOrgWebhooksPage from '@/app/settings/user/developer/organization-webhooks/page';
import AccountUsersPage from '@/app/settings/account/users/page';
import AccountUserDetailPage from '@/app/settings/account/users/[userId]/page';
import AccountLicensePage from '@/app/settings/account/license/page';
import AccountDevelopmentPage from '@/app/settings/account/development/page';
import DevelopmentAwsConfigPage from '@/app/settings/account/development/aws-config/page';
import DevelopmentAwsCredentialsPage from '@/app/settings/account/development/aws-credentials/page';
import DevelopmentAzureConfigPage from '@/app/settings/account/development/azure-config/page';
import DevelopmentGcpConfigPage from '@/app/settings/account/development/gcp-config/page';
import DevelopmentWorkerSettingsPage from '@/app/settings/account/development/worker-settings/page';
import DevelopmentLlmManagerPage from '@/app/settings/account/development/llm-manager/page';
import DevelopmentLlmManagerModelsPage from '@/app/settings/account/development/llm-manager/models/page';
import DevelopmentLlmProviderPage from '@/app/settings/account/development/llm-manager/providers/[providerName]/page';

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
