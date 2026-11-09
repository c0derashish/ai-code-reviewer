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
};

export type SubmitRepositoryRequest = {
  url: string;
};

export type SubmitRepositoryResponse = {
  id: string;
  status: JobStatus;
};