import "@testing-library/jest-dom";

if (typeof window !== "undefined") {
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
