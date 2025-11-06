// Backend API base URL - configurable via environment variable
// Defaults to http://localhost:8000 for FastAPI backend
// Set VITE_API_BASE_URL in .env file to point to your backend
// Example: VITE_API_BASE_URL=http://localhost:8000
export const API_BASE =
  import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

export const API_ENDPOINTS = {
  claims: {
    upload: "/upload",
    list: "/api/claims",
    get: (id: string) => `/api/claims/${id}`,
    reassign: (id: string) => `/api/claims/${id}/reassign`,
    chat: (id: string) => `/api/claims/${id}/chat`,
  },
  queues: {
    list: "/api/queues",
  },
  rules: {
    list: "/routing/rules",
    get: (id: string) => `/routing/rules/${id}`,
    create: "/routing/rules",
    update: (id: string) => `/routing/rules/${id}`,
    delete: (id: string) => `/routing/rules/${id}`,
    attributes: "/routing/attributes",
    apply: "/routing/apply",
  },
} as const;
