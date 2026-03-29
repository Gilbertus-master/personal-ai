export interface HealthResponse {
  status: string;
}

export interface VersionResponse {
  version: string;
  name: string;
}

export interface OmniusUser {
  user_id: number;
  email: string;
  display_name: string;
  role_name: string;
  role_level: number;
  department: string | null;
  permissions: string[];
}
