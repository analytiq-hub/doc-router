/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_FASTAPI_FRONTEND_URL?: string;
  readonly VITE_APP_NAME?: string;
  readonly VITE_APP_FAVICON?: string;
  readonly VITE_BACKEND_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
