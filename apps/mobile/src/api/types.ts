// TypeScript mirrors of the FastAPI response models. Kept in sync by hand
// with apps/api/{main,projects,files,users}.py — the API is the contract.

export type Mode = "short" | "memo" | "annotate";

export type Me = {
  sub: string;
  email: string;
  is_admin: boolean;
};

export type Source = {
  citation: string;
  url: string;
  source_type: string;
};

export type ChatResponse = {
  answer: string; // markdown, with citations already rendered as links
  mode: Mode;
  sources: Source[];
};

export type MatterType =
  | "divorce"
  | "custody"
  | "child_support"
  | "post_judgment"
  | "other"
  | null;

export type Project = {
  id: string;
  name: string;
  slug: string;
  description: string | null;
  matter_type: string | null;
  created_at: string;
  updated_at: string;
};

export type ProjectList = {
  items: Project[];
};

export type FileItem = {
  key: string; // full S3 key (needed for download/delete round-trips)
  name: string; // key relative to the project prefix (display name)
  size: number;
  last_modified: string;
};

export type CaseFileList = {
  bucket: string;
  prefix: string;
  items: FileItem[];
};

export type PresignUpload = {
  url: string;
  key: string;
  method: string; // "PUT"
  headers: Record<string, string>;
  expires_in: number;
};

export type PresignDownload = {
  url: string;
  expires_in: number;
};

export type ConvertResult = {
  key: string;
  name: string;
  scanned: boolean;
};

// A single turn rendered in the chat list.
export type ChatTurn = {
  id: string;
  role: "user" | "assistant";
  text: string;
  mode?: Mode;
  sources?: Source[];
  pending?: boolean;
  error?: boolean;
};
