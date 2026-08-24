import type {
  AlarmSeverity,
  CommandCapabilitiesResponse,
  EventCategory,
  EventListResponse,
  SessionUser,
  SystemStatus,
  TelemetryPoint,
  UserRecord,
  UserRole,
  UsersResponse,
} from "./types";


export class ApiError extends Error {
  readonly status: number;

  constructor(
    status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}


async function apiRequest<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers);
  if (options.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  const response = await fetch(`/api${path}`, {
    ...options,
    headers,
    credentials: "include",
  });

  if (!response.ok) {
    let message = `Request failed (${response.status})`;
    try {
      const payload = (await response.json()) as { detail?: unknown };
      if (typeof payload.detail === "string") {
        message = payload.detail;
      } else if (Array.isArray(payload.detail)) {
        message = payload.detail
          .map((item) => {
            if (typeof item === "object" && item !== null && "msg" in item && typeof item.msg === "string") {
              return item.msg;
            }
            return "Invalid request";
          })
          .join("; ");
      }
    } catch {
      // Retain the status-based fallback when the response is not JSON.
    }
    throw new ApiError(response.status, message);
  }

  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}


export const api = {
  login(username: string, password: string): Promise<SessionUser> {
    return apiRequest("/login", {
      method: "POST",
      body: JSON.stringify({ username, password }),
    });
  },

  getSession(): Promise<SessionUser> {
    return apiRequest("/session");
  },

  logout(): Promise<void> {
    return apiRequest("/logout", { method: "POST" });
  },

  getTelemetry(signal?: AbortSignal): Promise<TelemetryPoint> {
    return apiRequest("/telemetry", { signal });
  },

  getSystemStatus(signal?: AbortSignal): Promise<SystemStatus> {
    return apiRequest("/status", { signal });
  },

  getEvents(options: {
    limit?: number;
    beforeId?: number;
    category?: EventCategory;
    severity?: AlarmSeverity;
    signal?: AbortSignal;
  } = {}): Promise<EventListResponse> {
    const query = new URLSearchParams();
    query.set("limit", String(options.limit ?? 50));
    if (options.beforeId !== undefined) query.set("before_id", String(options.beforeId));
    if (options.category) query.set("category", options.category);
    if (options.severity) query.set("severity", options.severity);
    return apiRequest(`/events?${query.toString()}`, { signal: options.signal });
  },

  getCommandCapabilities(signal?: AbortSignal): Promise<CommandCapabilitiesResponse> {
    return apiRequest("/command-capabilities", { signal });
  },

  getUsers(): Promise<UserRecord[]> {
    return apiRequest("/users");
  },

  addUser(username: string, role: UserRole): Promise<UsersResponse> {
    return apiRequest("/users/add", {
      method: "POST",
      body: JSON.stringify({ username, role }),
    });
  },

  updateUser(username: string, role: UserRole): Promise<UsersResponse> {
    return apiRequest("/users/update", {
      method: "POST",
      body: JSON.stringify({ username, role }),
    });
  },

  removeUser(username: string): Promise<UsersResponse> {
    return apiRequest("/users/remove", {
      method: "POST",
      body: JSON.stringify({ username }),
    });
  },
};
