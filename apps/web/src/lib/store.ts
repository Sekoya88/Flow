import { create } from "zustand";

// ---- Types ----

export type NodeStatus = "idle" | "thinking" | "streaming" | "done" | "error";

export interface NodeState {
  status: NodeStatus;
  output?: string;
}

export interface User {
  id: string;
  email: string;
}

export interface Workspace {
  id: string;
  name: string;
}

// ---- Auth slice ----

interface AuthSlice {
  token: string | null;
  user: User | null;
  workspaces: Workspace[];
  currentWorkspaceId: string | null;
  setToken: (token: string | null) => void;
  setUser: (user: User | null) => void;
  setWorkspaces: (ws: Workspace[]) => void;
  setCurrentWorkspace: (id: string) => void;
}

// ---- Execution slice ----

interface ExecutionSlice {
  activeExecutionId: string | null;
  nodes: Record<string, NodeState>;
  tokens: string[];
  persistedLiveAnswer: string | null;
  setActiveExecution: (id: string | null) => void;
  setNode: (name: string, state: NodeState) => void;
  appendToken: (text: string) => void;
  setPersistedLiveAnswer: (text: string | null) => void;
  reset: () => void;
}

// ---- UI slice ----

export interface ActiveTask {
  type: 'run' | 'training' | 'research';
  label: string;
  href: string;
}

interface UISlice {
  inspectorOpen: boolean;
  toggleInspector: () => void;
  setInspectorOpen: (open: boolean) => void;
  activeTask: ActiveTask | null;
  setActiveTask: (task: ActiveTask | null) => void;
}

// ---- Combined store ----

type StoreState = AuthSlice & ExecutionSlice & UISlice;

export const useStore = create<StoreState>((set) => ({
  // Auth
  token: null,
  user: null,
  workspaces: [],
  currentWorkspaceId: null,
  setToken: (token) => set({ token }),
  setUser: (user) => set({ user }),
  setWorkspaces: (workspaces) => set({ workspaces }),
  setCurrentWorkspace: (id) => set({ currentWorkspaceId: id }),

  // Execution
  activeExecutionId: null,
  nodes: {},
  tokens: [],
  persistedLiveAnswer: null,
  setActiveExecution: (id) => set({ activeExecutionId: id }),
  setNode: (name, state) =>
    set((s) => ({ nodes: { ...s.nodes, [name]: state } })),
  appendToken: (text) => set((s) => ({ tokens: [...s.tokens, text] })),
  setPersistedLiveAnswer: (text) => set({ persistedLiveAnswer: text }),
  reset: () =>
    set({ activeExecutionId: null, nodes: {}, tokens: [], persistedLiveAnswer: null }),

  // UI
  inspectorOpen: true,
  toggleInspector: () => set((s) => ({ inspectorOpen: !s.inspectorOpen })),
  setInspectorOpen: (open) => set({ inspectorOpen: open }),
  activeTask: null,
  setActiveTask: (task) => set({ activeTask: task }),
}));

// Typed selector hooks
export const useAuth = () => useStore((s) => ({
  token: s.token,
  user: s.user,
  workspaces: s.workspaces,
  currentWorkspaceId: s.currentWorkspaceId,
  setToken: s.setToken,
  setUser: s.setUser,
  setWorkspaces: s.setWorkspaces,
  setCurrentWorkspace: s.setCurrentWorkspace,
}));

export const useExecution = () => useStore((s) => ({
  activeExecutionId: s.activeExecutionId,
  nodes: s.nodes,
  tokens: s.tokens,
  persistedLiveAnswer: s.persistedLiveAnswer,
  setActiveExecution: s.setActiveExecution,
  setNode: s.setNode,
  appendToken: s.appendToken,
  setPersistedLiveAnswer: s.setPersistedLiveAnswer,
  reset: s.reset,
}));

export const useUI = () => useStore((s) => ({
  inspectorOpen: s.inspectorOpen,
  toggleInspector: s.toggleInspector,
  setInspectorOpen: s.setInspectorOpen,
  activeTask: s.activeTask,
  setActiveTask: s.setActiveTask,
}));
