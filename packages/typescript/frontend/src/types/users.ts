export interface UserCreate {
  email: string;
  name: string;
  password: string;
}

export interface UserUpdate {
  name?: string;
  is_sysadmin?: boolean;
  email_verified?: boolean;
  password?: string;
  has_seen_tour?: boolean;
}

export interface UserResponse {
  id: string;
  email: string;
  name: string | null;
  is_sysadmin: boolean;
  email_verified: boolean | null;
  created_at: string;
  has_password: boolean;
  has_seen_tour: boolean;
}

export interface ListUsersParams {
  skip?: number;
  limit?: number;
  organization_id?: string;
  user_id?: string;
  search_name?: string;
}

export interface ListUsersResponse {
  users: UserResponse[];
  total_count: number;
  skip: number;
}
