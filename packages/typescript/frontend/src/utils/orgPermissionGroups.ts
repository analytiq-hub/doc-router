/** Built-in org permission group ids (phase 3). */

export const BUILTIN_VIEWER = 'viewer';
export const BUILTIN_OPERATOR = 'operator';
export const BUILTIN_BUILDER = 'builder';
export const BUILTIN_ADMIN = 'admin';

export type BuiltinPermissionGroupId =
  | typeof BUILTIN_VIEWER
  | typeof BUILTIN_OPERATOR
  | typeof BUILTIN_BUILDER
  | typeof BUILTIN_ADMIN;

export const BUILTIN_PERMISSION_GROUPS: {
  id: BuiltinPermissionGroupId;
  label: string;
}[] = [
  { id: BUILTIN_VIEWER, label: 'Viewer' },
  { id: BUILTIN_OPERATOR, label: 'Operator' },
  { id: BUILTIN_BUILDER, label: 'Builder' },
  { id: BUILTIN_ADMIN, label: 'Admin' },
];

export function permissionGroupLabel(id: string): string {
  return BUILTIN_PERMISSION_GROUPS.find((g) => g.id === id)?.label ?? id;
}

const PERMISSION_GROUP_DISPLAY_ORDER: BuiltinPermissionGroupId[] = [
  BUILTIN_ADMIN,
  BUILTIN_BUILDER,
  BUILTIN_OPERATOR,
  BUILTIN_VIEWER,
];

/** Stable order for displaying multiple groups (highest tier first). */
export function sortPermissionGroupIds(ids: string[]): string[] {
  const set = new Set(ids);
  const ordered: string[] = PERMISSION_GROUP_DISPLAY_ORDER.filter((id) => set.has(id));
  for (const id of ids) {
    if (!ordered.includes(id)) {
      ordered.push(id);
    }
  }
  return ordered;
}

export function memberHasAdminGroup(permissionGroupIds: string[] | undefined): boolean {
  return (permissionGroupIds ?? []).includes(BUILTIN_ADMIN);
}

/** Primary persona for display when a member has one built-in group. */
export function primaryPermissionGroupId(ids: string[] | undefined): BuiltinPermissionGroupId | null {
  if (!ids?.length) return null;
  const order: BuiltinPermissionGroupId[] = [
    BUILTIN_ADMIN,
    BUILTIN_BUILDER,
    BUILTIN_OPERATOR,
    BUILTIN_VIEWER,
  ];
  for (const id of order) {
    if (ids.includes(id)) return id;
  }
  return null;
}

export function normalizeOrgMember(member: {
  user_id: string;
  permission_group_ids?: string[];
}): { user_id: string; permission_group_ids: string[] } {
  const ids = member.permission_group_ids?.length
    ? member.permission_group_ids
    : [BUILTIN_OPERATOR];
  return { user_id: member.user_id, permission_group_ids: ids };
}

/** Whether a user has the org Admin permission group in this organization. */
export function userHasOrgAdminGroup(
  organization: { members: { user_id: string; permission_group_ids?: string[] }[] },
  userId: string,
): boolean {
  const member = organization.members.find((m) => m.user_id === userId);
  if (!member) return false;
  return memberHasAdminGroup(normalizeOrgMember(member).permission_group_ids);
}
