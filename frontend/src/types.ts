export type ExperienceLevel = "junior" | "middle" | "senior" | "lead";
export type JobType = "full_time" | "contract" | "freelance" | "internship";
export type EmploymentType = "full_day" | "part_time" | "remote";
export type Currency = "RUB" | "USD" | "EUR";

export interface JobSource {
  id: number;
  name: string;
  url: string;
  icon: string;
  is_active: boolean;
  last_sync: string | null;
}

export interface Job {
  id: number;
  source: string;
  title: string;
  company: string;
  salary_from: number | null;
  salary_to: number | null;
  currency: Currency;
  location: string;
  experience_level: ExperienceLevel | "";
  employment_type: EmploymentType | "";
  required_skills: string[];
  url: string;
  posted_at: string | null;
  is_favorited: boolean;
}

export interface JobDetail extends Omit<Job, "source"> {
  source: JobSource;
  description: string;
  job_type: JobType | "";
  nice_to_have: string[];
  external_id: string;
  created_at: string;
  updated_at: string;
  is_active: boolean;
}

export interface Paginated<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

export interface UserJobFilter {
  id: number;
  min_salary: number | null;
  max_salary: number | null;
  locations: string[];
  experience_levels: ExperienceLevel[];
  keywords: string[];
  excluded_keywords: string[];
  job_types: JobType[];
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface JobNotification {
  id: number;
  job: Job;
  notified_at: string;
  sent_to_telegram: boolean;
  is_read: boolean;
}

export interface Stats {
  total_active: number;
  new_today: number;
  new_this_week: number;
  by_source: { source: string; count: number }[];
  by_experience_level: { experience_level: string; count: number }[];
  sources: { name: string; is_active: boolean; last_sync: string | null }[];
}

export interface JobFiltersQuery {
  search?: string;
  min_salary?: number;
  max_salary?: number;
  location?: string;
  experience_level?: ExperienceLevel[];
  job_type?: JobType[];
  employment_type?: EmploymentType[];
  source?: number;
  ordering?: string;
  page?: number;
}

export type WsEvent =
  | { type: "new_job"; data: Job }
  | { type: "job_updated"; data: Job }
  | { type: "job_removed"; data: { id: number } };
