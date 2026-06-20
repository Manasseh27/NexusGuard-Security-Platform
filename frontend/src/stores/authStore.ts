import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { CurrentUser } from "../types";
import { authApi } from "../services/api";

interface AuthState {
  user:         CurrentUser | null;
  accessToken:  string | null;
  refreshToken: string | null;
  isLoading:    boolean;
  error:        string | null;

  login:  (username: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  fetchMe: () => Promise<void>;
  clearError: () => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      user:         null,
      accessToken:  null,
      refreshToken: null,
      isLoading:    false,
      error:        null,

      login: async (username, password) => {
        set({ isLoading: true, error: null });
        try {
          const tokens = await authApi.login(username, password);
          localStorage.setItem("access_token", tokens.access_token);
          localStorage.setItem("refresh_token", tokens.refresh_token);
          set({ accessToken: tokens.access_token, refreshToken: tokens.refresh_token });
          await get().fetchMe();
        } catch (err: unknown) {
          const msg = err instanceof Error ? err.message : "Login failed";
          set({ error: msg });
          throw err;
        } finally {
          set({ isLoading: false });
        }
      },

      logout: async () => {
        try { await authApi.logout(); } catch { /* ignore */ }
        localStorage.removeItem("access_token");
        localStorage.removeItem("refresh_token");
        set({ user: null, accessToken: null, refreshToken: null });
      },

      fetchMe: async () => {
        try {
          const user = await authApi.me();
          set({ user });
        } catch {
          set({ user: null });
        }
      },

      clearError: () => set({ error: null }),
    }),
    {
      name: "cisco-auth",
      partialize: (state) => ({
        accessToken:  state.accessToken,
        refreshToken: state.refreshToken,
      }),
    }
  )
);
