import { useAuthStore } from "../stores/authStore";

/**
 * Returns true if the current user holds the given permission.
 * Mirrors backend CurrentUser.has_permission():
 *   - ["*"] grants everything (admin / super_admin)
 *   - otherwise checks for exact permission string
 */
export function usePermission(permission: string): boolean {
  const user = useAuthStore((s) => s.user);
  if (!user) return false;
  if (user.permissions.includes("*")) return true;
  return user.permissions.includes(permission);
}

/**
 * Returns true if the user holds ANY of the given permissions.
 */
export function useAnyPermission(...permissions: string[]): boolean {
  const user = useAuthStore((s) => s.user);
  if (!user) return false;
  if (user.permissions.includes("*")) return true;
  return permissions.some((p) => user.permissions.includes(p));
}
