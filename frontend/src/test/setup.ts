import "@testing-library/jest-dom";

class LocalStorageMock {
  private store: Record<string, string> = {};
  clear() {
    this.store = {};
  }
  getItem(key: string) {
    return this.store[key] ?? null;
  }
  setItem(key: string, value: string) {
    this.store[key] = String(value);
  }
  removeItem(key: string) {
    delete this.store[key];
  }
  get length() {
    return Object.keys(this.store).length;
  }
  key(index: number) {
    return Object.keys(this.store)[index] ?? null;
  }
}

const mockLocalStorage = new LocalStorageMock();
const mockSessionStorage = new LocalStorageMock();

Object.defineProperty(globalThis, "localStorage", {
  value: mockLocalStorage,
  writable: true,
  configurable: true,
});
Object.defineProperty(globalThis, "sessionStorage", {
  value: mockSessionStorage,
  writable: true,
  configurable: true,
});

if (typeof window !== "undefined") {
  Object.defineProperty(window, "localStorage", {
    value: mockLocalStorage,
    writable: true,
    configurable: true,
  });
  Object.defineProperty(window, "sessionStorage", {
    value: mockSessionStorage,
    writable: true,
    configurable: true,
  });
  if (!window.URL.createObjectURL) {
    window.URL.createObjectURL = () => "blob:mock-url";
  }
  if (!window.URL.revokeObjectURL) {
    window.URL.revokeObjectURL = () => {};
  }
}

const originalFetch = global.fetch;
global.fetch = async (input: RequestInfo | URL, init?: RequestInit) => {
  const url =
    typeof input === "string"
      ? input
      : input instanceof URL
        ? input.href
        : input.url;
  if (
    url &&
    (url.includes(".webp") ||
      url.includes(".png") ||
      url.includes(".jpg") ||
      url.includes("/photos/") ||
      url.includes("/api/media/"))
  ) {
    return new Response(new Blob(["mock-image-data"], { type: "image/webp" }), {
      status: 200,
      headers: { "Content-Type": "image/webp" },
    });
  }
  if (originalFetch) {
    return originalFetch(input, init);
  }
  return new Response("Not Found", { status: 404 });
};
