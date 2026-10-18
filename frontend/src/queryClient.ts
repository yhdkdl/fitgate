import { QueryClient } from "@tanstack/react-query";

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 1000 * 60 * 5,
      refetchOnWindowFocus: false,
    },
  },
});

export function clearAppQueryCache(): void {
  try {
    queryClient.clear();
  } catch {
    // Ignore in non-browser/test environments
  }
}
