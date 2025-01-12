export interface UserCreate {
  email: string;
  name: string;
  password: string;
  role?: string;
  organization_type: 'team' | 'enterprise';
  organizations: {
    id: string;
    role: 'admin' | 'user';
  }[];
}

export interface UserUpdate {
  name?: string;
  role?: string;
  emailVerified?: boolean;
  password?: string;
  organization_id?: string;
  organization_type?: 'team' | 'enterprise';
}

export interface UserResponse {
  id: string;
  email: string;
  name: string | null;
  role: string;
  emailVerified: boolean | null;
  createdAt: string;
  hasPassword: boolean;
}

export interface ListUsersParams {
  skip?: number;
  limit?: number;
  organization_id?: string;
  user_id?: string;
}

export interface ListUsersResponse {
  users: UserResponse[];
  total_count: number;
  skip: number;
}
