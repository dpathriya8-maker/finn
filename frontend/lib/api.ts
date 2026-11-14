/**
 * Base URL of the FastAPI backend, without a trailing slash.
 * Set NEXT_PUBLIC_API_URL on Vercel; local development falls back to the dev server on port 8000.
 * An empty string means "not configured", and the UI says so instead of guessing.
 */
const configured = process.env.NEXT_PUBLIC_API_URL?.trim().replace(/\/+$/, "");

export const API_URL: string =
  configured || (process.env.NODE_ENV === "development" ? "http://localhost:8000" : "");
