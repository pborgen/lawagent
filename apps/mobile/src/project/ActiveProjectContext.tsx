import * as SecureStore from "expo-secure-store";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

// The active project is just a UUID the user has selected. The backend
// re-verifies ownership on every request, so it's safe to persist plainly.
// (Stored via SecureStore for convenience — it's already a dependency.)
const KEY = "lawagent.activeProject";

type ActiveProjectValue = {
  activeProjectId: string | null;
  activeProjectName: string | null;
  setActiveProject: (id: string | null, name?: string | null) => void;
};

const Ctx = createContext<ActiveProjectValue | null>(null);

export function ActiveProjectProvider({ children }: { children: ReactNode }) {
  const [activeProjectId, setId] = useState<string | null>(null);
  const [activeProjectName, setName] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      const saved = await SecureStore.getItemAsync(KEY);
      if (saved) {
        try {
          const { id, name } = JSON.parse(saved) as {
            id: string;
            name: string | null;
          };
          setId(id);
          setName(name ?? null);
        } catch {
          // ignore corrupt value
        }
      }
    })();
  }, []);

  const setActiveProject = useCallback(
    (id: string | null, name: string | null = null) => {
      setId(id);
      setName(name);
      if (id) {
        void SecureStore.setItemAsync(KEY, JSON.stringify({ id, name }));
      } else {
        void SecureStore.deleteItemAsync(KEY);
      }
    },
    [],
  );

  const value = useMemo(
    () => ({ activeProjectId, activeProjectName, setActiveProject }),
    [activeProjectId, activeProjectName, setActiveProject],
  );

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useActiveProject(): ActiveProjectValue {
  const ctx = useContext(Ctx);
  if (!ctx) {
    throw new Error("useActiveProject must be used within ActiveProjectProvider");
  }
  return ctx;
}
