export type Fact = {
  id: string;
  field: string;
  value: string;
  original: string;
  normalized: string;
  filename: string;
  document: string;
  job_id: string;
  record_id: string;
  page: number | null;
  row: number | null;
  column: string | null;
  span: number[] | null;
  confidence: number | null;
  method: string;
  review_state: string;
  committed: boolean;
  active: boolean;
  person_id: string | null;
  approved_by?: string;
  approval_reason?: string;
  column_mapping: Record<string, string>;
};
export type Candidate = {
  person_id: string;
  name: string;
  score: number;
  matching: string[];
  conflicting: string[];
  missing: string[];
  sources: Record<string, string[]>;
  recommended: string;
};
export type ImportRecord = {
  id: string;
  values: Record<string, string | null>;
  original: Record<string, string | null>;
  row: number | null;
  page: number | null;
  text: string | null;
  confidence: number | null;
  method: string;
  committed: boolean;
  duplicate: boolean;
  blank: boolean;
  facts: Fact[];
  person_id: string | null;
  outcome?: string;
  decision: {
    action: string;
    target: string | null;
    actor: string;
    reason: string;
  } | null;
  recommendation: {
    action: string;
    candidates: Candidate[];
    target: string | null;
    reason: string;
  };
};
export type Job = {
  id: string;
  filename: string;
  hash: string;
  created: string;
  status: string;
  progress: number;
  record_count?: number;
  records: ImportRecord[];
  headers: string[];
  mapping: Record<string, string>;
  pages: {
    number: number;
    text: string;
    method: string;
    confidence: number | null;
  }[];
  warnings: string[];
  error: string | null;
  result?: Record<string, number>;
};
export type Person = {
  id: string;
  name: string;
  roles: string[];
  facts: Fact[];
  source_count: number;
};
export type GraphNode = {
  id: string;
  label: string;
  type: string;
  status: string;
};
export type GraphEdge = {
  id: string;
  source: string;
  target: string;
  label: string;
  evidence: string[];
  status: string;
  date?: string | null;
};
export type Graph = {
  nodes: GraphNode[];
  edges: GraphEdge[];
  truncated?: boolean;
  total_nodes?: number;
};
export type Audit = {
  id: string;
  action: string;
  actor: string;
  reason: string;
  time: string;
  job_id?: string;
  record_id?: string;
  target?: string;
  result?: Record<string, number>;
  undone?: boolean;
  changes?: {
    record_id: string;
    person_id: string;
    claims: string[];
    new: boolean;
  }[];
};
export type Case = {
  reference: string;
  people: string[];
  documents: string[];
  evidence: string[];
};
export type Dashboard = {
  people: number;
  documents: number;
  facts: number;
  pending: number;
  relationships: number;
  nodes: number;
  warnings: number;
  backend: string;
  demo: boolean;
  revision: number;
  recent_imports: Job[];
  analytics: {
    component_count: number;
    degree_centrality: {
      id: string;
      name: string;
      degree: number;
      clustering: number;
    }[];
    average_clustering: number;
    bounded: boolean;
  };
};
export type Health = {
  backend: string;
  demo: boolean;
  fields: string[];
  auto_threshold: number;
  extraction_provider: string;
};
export const fields = [
  "profile_id",
  "name",
  "aliases",
  "phone",
  "account",
  "bank",
  "address",
  "birth_date",
  "vehicle",
  "organisation",
  "case",
  "date",
  "role",
  "source_id",
  "relationship",
  "caller_phone",
  "callee_phone",
  "from_account",
  "to_account",
  "from_bank",
  "to_bank",
  "amount",
  "duration",
];
export const label = (value: string) =>
  value.replaceAll("_", " ").replace(/\b\w/g, (x) => x.toUpperCase());
export const number = (value: number) => new Intl.NumberFormat().format(value);
export const date = (value: string) =>
  new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
export async function api<T>(
  path: string,
  body?: unknown,
  method = "POST",
): Promise<T> {
  const response = await fetch(
    "/api" + path,
    body === undefined
      ? undefined
      : {
          method,
          headers:
            body instanceof FormData
              ? undefined
              : { "Content-Type": "application/json" },
          body: body instanceof FormData ? body : JSON.stringify(body),
        },
  );
  if (!response.ok) {
    const data = await response.json().catch(() => ({
      detail: "Service returned an unreadable response. Retry the request.",
    }));
    throw new Error(
      typeof data.detail === "string"
        ? data.detail
        : Array.isArray(data.detail)
          ? data.detail
              .map(
                (item: { loc?: (string | number)[]; msg?: string }) =>
                  `${item.loc?.slice(1).join(".") || "Input"}: ${item.msg || "Invalid value"}`,
              )
              .join("; ")
          : "Request validation failed. Check your input and retry.",
    );
  }
  return response.json() as Promise<T>;
}
