export type JobStatus = "queued" | "running" | "done" | "failed";

export type StartAnalysisResponse = {
  id: string;
  status: JobStatus;
};

export type IssueDto = {
  id?: string;
  file_path: string;
  line: number;
  severity: string;
  category: string;
  title: string;
  explanation: string;
  suggestion?: string | null;
  before?: string | null;
  after?: string | null;
};

export type AnalysisResultResponse = {
  id: string;
  status: JobStatus;
  score?: number | null;
  issues?: IssueDto[];
  error?: string | null;
  summary?: AnalysisSummary | null;
};

export type SubmitRepositoryRequest = {
  url: string;
};

export type SubmitRepositoryResponse = {
  id: string;
  status: JobStatus;
};

export type RepositoryStatusResponse = {
  id: string;
  status: JobStatus;
  project_name?: string | null;
  file_count?: number | null;
  skipped_count?: number | null;
  error?: string | null;
};

export type RepositoryFileDto = {
  path: string;
  language: string;
  content: string;
};

export type RepositoryFilesResponse = {
  project_name: string;
  files: RepositoryFileDto[];
};

// The extra numbers the server sends with a finished analysis. Only the saving fields are used.
export type AnalysisSummary = {
  saved?: boolean;
  saved_analysis_id?: string;
  save_error?: string;
  [key: string]: unknown;
};