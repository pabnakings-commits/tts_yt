export interface Voice {
  id: string;
  name: string;
  gender: "male" | "female";
  style: string;
  language: string;
  description: string;
}

export interface VoiceList {
  engine: string;
  model: string;
  voices: Voice[];
}

export type JobState =
  | "queued"
  | "preparing_model"
  | "generating"
  | "processing_audio"
  | "combining_segments"
  | "finalizing"
  | "done"
  | "error";

export interface JobProgress {
  job_id: string;
  state: JobState;
  progress: number;
  message: string;
  error?: string | null;
  project_id?: string | null;
  audio_id?: string | null;
  result?: {
    audio_id: string;
    project_id?: string | null;
    duration_seconds: number;
    has_mp3: boolean;
    metadata: Record<string, unknown>;
  } | null;
}

export interface ProjectSummary {
  id: string;
  name: string;
  created_at: string;
  updated_at: string;
  has_audio: boolean;
  has_mp3: boolean;
  voice_id?: string | null;
}

export interface ProjectDetail extends ProjectSummary {
  script: string;
  speed: number;
  metadata?: Record<string, unknown> | null;
}

export interface SettingsModel {
  engine: string;
  device: string;
  output_format: "wav" | "mp3" | "wav+mp3";
  output_dir: string;
  max_concurrent_generations: number;
}

export interface SystemStatus {
  python_version: string;
  device: string;
  gpu_detected: boolean;
  gpu_name?: string | null;
  ffmpeg_installed: boolean;
  ffmpeg_version?: string | null;
  model_ready: boolean;
  engine: string;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`/api${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) {
    let detail = `Request failed (${res.status})`;
    try {
      const body = await res.json();
      if (body?.detail) detail = body.detail;
    } catch {
      // ignore
    }
    throw new Error(detail);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export const api = {
  getVoices: () => request<VoiceList>("/voices"),
  getSystem: () => request<SystemStatus>("/system"),
  getSettings: () => request<SettingsModel>("/settings"),
  updateSettings: (body: Partial<SettingsModel>) =>
    request<SettingsModel>("/settings", { method: "POST", body: JSON.stringify(body) }),
  generate: (body: {
    text: string;
    voice_id: string;
    speed: number;
    output_format?: string;
    project_name?: string;
  }) =>
    request<{ job_id: string }>("/generate", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  getJob: (jobId: string) => request<JobProgress>(`/jobs/${jobId}`),
  listProjects: () => request<ProjectSummary[]>("/projects"),
  createProject: (body: { name: string; script?: string; voice_id?: string; speed?: number }) =>
    request<ProjectDetail>("/projects", { method: "POST", body: JSON.stringify(body) }),
  getProject: (id: string) => request<ProjectDetail>(`/projects/${id}`),
  deleteProject: (id: string) => request<void>(`/projects/${id}`, { method: "DELETE" }),
  audioUrl: (audioId: string, fmt: "wav" | "mp3") => `/api/audio/${audioId}/${fmt}`,
};

export async function pollJob(
  jobId: string,
  onUpdate: (job: JobProgress) => void,
  intervalMs = 800
): Promise<JobProgress> {
  while (true) {
    const job = await api.getJob(jobId);
    onUpdate(job);
    if (job.state === "done" || job.state === "error") {
      return job;
    }
    await new Promise((r) => setTimeout(r, intervalMs));
  }
}
