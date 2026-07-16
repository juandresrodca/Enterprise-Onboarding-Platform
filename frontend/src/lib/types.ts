/** API contracts mirrored from the FastAPI backend (app/models). */

export type Role = "helpdesk" | "hr" | "admin" | "global_admin";

export interface SessionInfo {
  username: string;
  display_name: string;
  role: Role;
  role_label: string;
  permissions: string[];
  expires_at: string;
  demo_mode: boolean;
  auth_source: string;
  csrf_token?: string | null;
}

export interface UserSummary {
  sam_account_name: string;
  display_name: string;
  user_principal_name: string;
  email: string | null;
  department: string | null;
  job_title: string | null;
  office?: string | null;
  ou: string | null;
  manager?: string | null;
  enabled: boolean;
  created_at: string | null;
  source: string;
  employee_type?: string | null;
}

export interface UserDetail extends UserSummary {
  groups: string[];
  group_detail?: { name: string; category: string }[];
  licenses: string[];
  license_detail?: { sku_part_number: string; display_name: string }[];
  shared_mailboxes: string[];
  proxy_addresses: string[];
  extension_attributes: Record<string, string>;
  mailbox: boolean;
  home_folder: { path: string; drive: string } | null;
  profile: { roaming_profile_path?: string | null; logon_script?: string | null };
  phone?: string | null;
  mobile?: string | null;
  company?: string | null;
  city?: string | null;
  country?: string | null;
}

export interface OUNode {
  name: string;
  dn: string;
  children: OUNode[];
}

export interface GroupInfo {
  name: string;
  category: "security" | "distribution" | "m365";
  scope: string;
  description: string;
  dn: string;
  member_count: number | null;
}

export interface LicenseInfo {
  sku_part_number: string;
  display_name: string;
  total: number;
  assigned: number;
}

export interface NewUserSpec {
  first_name: string;
  last_name: string;
  display_name?: string | null;
  sam_account_name?: string | null;
  user_principal_name?: string | null;
  email?: string | null;
  ou?: string | null;
  department?: string | null;
  company?: string | null;
  office?: string | null;
  office_location?: string | null;
  job_title?: string | null;
  employee_id?: string | null;
  employee_type?: string | null;
  cost_center?: string | null;
  description?: string | null;
  manager?: string | null;
  phone?: string | null;
  mobile?: string | null;
  country?: string | null;
  city?: string | null;
  state?: string | null;
  address?: string | null;
  postal_code?: string | null;
  account_expiration?: string | null;
  groups: string[];
  licenses: string[];
  create_mailbox: boolean;
  shared_mailboxes: string[];
  proxy_addresses?: string[];
  extension_attributes?: Record<string, string>;
  home_folder: { enabled: boolean; base_path?: string | null; drive_letter: string };
  profile: { roaming_profile_path?: string | null; logon_script?: string | null };
  password: {
    generate: boolean;
    value?: string | null;
    force_change_at_logon: boolean;
    never_expires: boolean;
  };
}

export interface ValidationIssue {
  index: number;
  field: string;
  code: string;
  severity: "error" | "warning";
  message: string;
}

export interface ValidationResult {
  valid: boolean;
  issues: ValidationIssue[];
  users: NewUserSpec[];
}

export interface PlanAction {
  kind: string;
  summary: string;
  details: string[];
}

export interface UserPlan {
  display_name: string;
  sam_account_name: string;
  user_principal_name: string;
  email: string | null;
  ou: string;
  manager: string | null;
  actions: PlanAction[];
  warnings: string[];
}

export interface ExecutionPlan {
  summary: string;
  total_users: number;
  total_actions: number;
  users: UserPlan[];
  issues: ValidationIssue[];
}

export interface UserResult {
  sam_account_name: string;
  user_principal_name: string;
  display_name: string;
  status: "success" | "error";
  message: string;
  generated_password?: string | null;
}

export interface JobLogEntry {
  ts: string;
  level: "info" | "success" | "warning" | "error";
  message: string;
}

export interface Job {
  id: string;
  type: string;
  status: "queued" | "running" | "completed" | "completed_with_errors" | "failed";
  created_by: string;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
  total: number;
  done: number;
  errors: number;
  logs: JobLogEntry[];
  results: UserResult[];
}

export interface AuditEntry {
  id: number;
  ts: string;
  actor: string;
  actor_role: string;
  action: string;
  target: string;
  status: string;
  computer: string;
  source_ip: string;
  details: Record<string, unknown> | null;
}

export interface DashboardData {
  stats: {
    total_users: number;
    enabled_users: number;
    created_last_7_days: number;
    contractors: number;
    groups: number;
    licenses: LicenseInfo[];
    recent_users: UserSummary[];
  };
  pending_jobs: number;
  recent_jobs: Job[];
  errors_24h: number;
  recent_activity: AuditEntry[];
}
