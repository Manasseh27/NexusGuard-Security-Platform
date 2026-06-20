/**
 * Users Management Page
 * User accounts, roles, and access control administration.
 */

import { useState, useEffect } from "react";
import { C } from "../styles/tokens";
import { usersApi } from "../services/api";

interface User {
  id: string;
  username: string;
  email: string;
  role: string;
  is_active: boolean;
}

export default function UsersPage() {
  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [formData, setFormData] = useState({
    username: "",
    email: "",
    password: "",
    role: "viewer",
  });

  useEffect(() => {
    fetchUsers();
  }, []);

  const fetchUsers = async () => {
    try {
      setLoading(true);
      const result = await usersApi.list({ limit: 100 });
      setUsers(Array.isArray(result) ? result : result?.users || []);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load users");
    } finally {
      setLoading(false);
    }
  };

  const handleCreateUser = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await usersApi.create(formData.username, formData.email, formData.password, formData.role);
      setFormData({ username: "", email: "", password: "", role: "viewer" });
      setShowCreateForm(false);
      fetchUsers();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create user");
    }
  };

  const handleDeleteUser = async (userId: string) => {
    if (!window.confirm("Are you sure you want to delete this user?")) return;
    try {
      await usersApi.delete(userId);
      fetchUsers();
    } catch (err) {
      console.error("Failed to delete user:", err);
    }
  };

  const getRoleColor = (role: string) => {
    switch (role?.toLowerCase()) {
      case "admin": return "#ef4444";
      case "engineer": return "#f59e0b";
      case "analyst": return "#06b6d4";
      case "viewer": return "#6b7280";
      default: return C.textMuted;
    }
  };

  return (
    <div style={{ background: C.bg, minHeight: "100vh", color: C.text, padding: 24 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 24 }}>
        <h1 style={{ fontSize: 28, fontWeight: 600 }}>User Management</h1>
        <button
          onClick={() => setShowCreateForm(!showCreateForm)}
          style={{
            padding: "8px 16px",
            background: C.cyan,
            color: "white",
            border: "none",
            borderRadius: 4,
            cursor: "pointer",
            fontSize: 14,
            fontWeight: 500,
          }}
        >
          {showCreateForm ? "Cancel" : "Add User"}
        </button>
      </div>

      {showCreateForm && (
        <form
          onSubmit={handleCreateUser}
          style={{
            background: C.surface2,
            border: `1px solid ${C.border}`,
            borderRadius: 8,
            padding: 16,
            marginBottom: 24,
          }}
        >
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, marginBottom: 16 }}>
            <input
              type="text"
              placeholder="Username"
              value={formData.username}
              onChange={(e) => setFormData({ ...formData, username: e.target.value })}
              required
              style={{
                padding: 8,
                background: C.surface3,
                border: `1px solid ${C.border}`,
                color: C.text,
                borderRadius: 4,
              }}
            />
            <input
              type="email"
              placeholder="Email"
              value={formData.email}
              onChange={(e) => setFormData({ ...formData, email: e.target.value })}
              required
              style={{
                padding: 8,
                background: C.surface3,
                border: `1px solid ${C.border}`,
                color: C.text,
                borderRadius: 4,
              }}
            />
            <input
              type="password"
              placeholder="Password"
              value={formData.password}
              onChange={(e) => setFormData({ ...formData, password: e.target.value })}
              required
              style={{
                padding: 8,
                background: C.surface3,
                border: `1px solid ${C.border}`,
                color: C.text,
                borderRadius: 4,
              }}
            />
            <select
              value={formData.role}
              onChange={(e) => setFormData({ ...formData, role: e.target.value })}
              style={{
                padding: 8,
                background: C.surface3,
                border: `1px solid ${C.border}`,
                color: C.text,
                borderRadius: 4,
              }}
            >
              <option value="viewer">Viewer</option>
              <option value="analyst">Analyst</option>
              <option value="engineer">Engineer</option>
              <option value="admin">Admin</option>
            </select>
          </div>
          <button
            type="submit"
            style={{
              padding: "8px 16px",
              background: C.cyan,
              color: "white",
              border: "none",
              borderRadius: 4,
              cursor: "pointer",
            }}
          >
            Create User
          </button>
        </form>
      )}

      <div style={{
        background: C.surface2,
        border: `1px solid ${C.border}`,
        borderRadius: 8,
        padding: 16,
      }}>
        {error && (
          <div style={{
            background: "#7f1d1d",
            color: "#fecaca",
            padding: 12,
            borderRadius: 4,
            marginBottom: 16,
          }}>
            {error}
          </div>
        )}

        {loading ? (
          <div style={{ textAlign: "center", padding: 40 }}>Loading users...</div>
        ) : users.length === 0 ? (
          <div style={{ textAlign: "center", padding: 40, color: C.textMuted }}>
            No users found
          </div>
        ) : (
          <div style={{ overflowX: "auto" }}>
            <table style={{
              width: "100%",
              borderCollapse: "collapse",
              fontSize: 13,
            }}>
              <thead>
                <tr style={{ borderBottom: `1px solid ${C.border}` }}>
                  <th style={{ textAlign: "left", padding: 12, fontWeight: 600 }}>Username</th>
                  <th style={{ textAlign: "left", padding: 12, fontWeight: 600 }}>Email</th>
                  <th style={{ textAlign: "left", padding: 12, fontWeight: 600 }}>Role</th>
                  <th style={{ textAlign: "center", padding: 12, fontWeight: 600 }}>Status</th>
                  <th style={{ textAlign: "center", padding: 12, fontWeight: 600 }}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {users.map((user) => (
                  <tr key={user.id} style={{ borderBottom: `1px solid ${C.border}` }}>
                    <td style={{ padding: 12 }}>{user.username}</td>
                    <td style={{ padding: 12 }}>{user.email}</td>
                    <td style={{ padding: 12 }}>
                      <span style={{
                        display: "inline-block",
                        padding: "2px 6px",
                        borderRadius: 3,
                        background: getRoleColor(user.role),
                        color: "white",
                        fontSize: 11,
                        fontWeight: 500,
                      }}>
                        {user.role?.toUpperCase()}
                      </span>
                    </td>
                    <td style={{ padding: 12, textAlign: "center" }}>
                      <span style={{
                        display: "inline-block",
                        padding: "2px 6px",
                        borderRadius: 3,
                        background: user.is_active ? "#10b981" : "#6b7280",
                        color: "white",
                        fontSize: 11,
                      }}>
                        {user.is_active ? "Active" : "Inactive"}
                      </span>
                    </td>
                    <td style={{ padding: 12, textAlign: "center" }}>
                      <button
                        onClick={() => handleDeleteUser(user.id)}
                        style={{
                          padding: "4px 8px",
                          background: "#ef4444",
                          color: "white",
                          border: "none",
                          borderRadius: 3,
                          cursor: "pointer",
                          fontSize: 12,
                        }}
                      >
                        Delete
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
