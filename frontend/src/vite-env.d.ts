/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Set to "1" to use frontend mocks (e.g. bare-soil) instead of the API. */
  readonly VITE_USE_MOCKS?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
