import { ApiError } from "./api";

export function errorText(err: unknown, fallback = "Something went wrong. Try again."): string {
  return err instanceof ApiError ? err.message : fallback;
}
