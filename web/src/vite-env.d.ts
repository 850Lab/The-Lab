/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Full origin of workflow FastAPI (no path), e.g. https://repl-8000.replit.dev */
  readonly VITE_WORKFLOW_API_URL?: string;
  readonly VITE_WORKFLOW_API_PREFIX?: string;
  readonly VITE_WORKFLOW_ADMIN_KEY?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
