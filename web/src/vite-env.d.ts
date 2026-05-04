/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_LINA_API_BASE?: string;
  readonly VITE_LINA_API_KEY?: string;
  readonly VITE_LINA_USER_ID?: string;
  readonly VITE_LINA_PASSPHRASE?: string;
  readonly VITE_LINA_FIRST_NAME?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
