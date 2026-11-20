// Test-only stand-in for @kirocrew/app-sdk (the host provides the real one at runtime).
// Tests replace the doubles through `stub.api` and `stub.openChat`.
export interface ApiDouble {
  get: (path: string) => Promise<unknown>;
}

export interface ChatLaunchOptions {
  message?: string;
  autoSend?: boolean;
  [key: string]: unknown;
}

export const stub: {
  api: ApiDouble;
  openChat: (opts?: ChatLaunchOptions) => void;
} = {
  api: { get: () => Promise.reject(new Error("api.get not stubbed")) },
  openChat: () => {},
};

export function useAppApi(): ApiDouble {
  return { get: (path: string) => stub.api.get(path) };
}

export function useChatLauncher(): { openChat: (opts?: ChatLaunchOptions) => void } {
  return { openChat: (opts?: ChatLaunchOptions) => stub.openChat(opts) };
}
