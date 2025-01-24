export interface CreateTokenRequest {
    name: string;
    lifetime: number;
    organization_id?: string;
}

export interface AccessToken {
    id: string;
    user_id: string;
    organization_id?: string;
    name: string;
    token: string;
    created_at: string;
    lifetime: number;
}