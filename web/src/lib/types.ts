export type Role = "admin" | "tutor" | "leader";
export type Gender = "male" | "female";
export type DocKind = "passport" | "photo" | "cv";
export type DocType = "passport" | "id_card";
export type CertType = "ielts" | "toefl" | "sat" | "duolingo" | "cefr" | "national" | "olympiad" | "other";
export type CertStatus = "pending" | "approved" | "rejected";

export interface Me {
  id: number;
  username: string;
  name: string | null;
  role: Role;
  is_admin: boolean;
  is_tutor: boolean;
  leader_groups: { id: number; name: string }[];
  must_change_password: boolean;
  telegram_connected: boolean;
}

export interface AppConfig {
  bot_username: string | null;
}

export interface DocumentInfo {
  present: boolean;
  pages: { index: number; mime: string | null; name: string | null; source: string; side: string | null }[];
  updated_at: string | null;
}

export interface Student {
  id: number;
  full_name: string;
  last_name: string;
  first_name: string;
  middle_name: string | null;
  birth_date: string;
  age: number;
  gender: Gender;
  phone: string;
  group: { id: number; name: string };
  document: {
    type: DocType | null;
    number: string | null;
    expiry: string | null;
    pinfl: string | null;
    nationality: string | null;
  };
  telegram: { id: number; username: string | null; first_name: string | null };
  documents: Record<DocKind, DocumentInfo>;
  created_at: string;
  updated_at: string;
}

export interface HistoryEntry {
  at: string;
  actor: string;
  action: string;
  details: Record<string, unknown> | null;
}

export interface StudentDetail extends Student {
  certificates: Certificate[];
  can_edit: boolean;
  can_delete: boolean;
  history: HistoryEntry[];
}

export interface FilePage {
  index: number;
  mime: string | null;
  name: string | null;
}

export interface Certificate {
  id: number;
  type: CertType;
  result: string;
  status: CertStatus;
  note: string | null;
  files: (FilePage & { source: string })[];
  reviewed_by: string | null;
  reviewed_at: string | null;
  created_at: string;
  /** In the certificates list (not on a student's page). */
  student?: { id: number; full_name: string; group: { id: number; name: string } };
  can_review?: boolean;
}

export interface CertificatePage extends Page<Certificate> {
  counts: Record<CertStatus, number>;
}

export interface Page<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

export interface Group {
  id: number;
  name: string;
  is_active: boolean;
  students: number;
  leaders: { id: number; label: string; username: string; telegram_connected: boolean }[];
  created_at: string;
}

export interface Account {
  id: number;
  username: string;
  display_name: string | null;
  label: string;
  roles: { role: Role; group: { id: number; name: string } | null }[];
  is_active: boolean;
  must_change_password: boolean;
  telegram: { id: number; username: string | null } | null;
  last_login_at: string | null;
  created_at: string;
  temporary_password?: string;
}

export interface Stats {
  students: number;
  groups: number;
  today: number;
  last_7_days: number;
  per_day: { date: string; count: number }[];
  gender: Record<Gender, number>;
  documents: { complete: number; no_photo: number; no_cv: number };
  by_group: { id: number; name: string; students: number }[];
  certificates: { pending: number; approved: number };
}

export interface Prefs {
  registration_open: boolean;
  notify_leaders: boolean;
  max_document_pages: number;
  min_student_age: number;
  max_student_age: number;
}

export interface SettingsPayload {
  prefs: Prefs;
  environment: { timezone: string };
}

export interface AuditEntry {
  id: number;
  at: string;
  actor: string;
  action: string;
  entity: string | null;
  entity_id: number | null;
  summary: string | null;
  details: Record<string, unknown> | null;
}
