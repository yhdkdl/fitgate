/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: "var(--bg)",
        surface: "var(--surface)",
        "surface-2": "var(--surface-2)",
        border: "var(--border)",
        primary: {
          DEFAULT: "var(--primary)",
          hover: "var(--primary-hover)",
        },
        ring: "var(--ring)",
        text: "var(--text)",
        "text-muted": "var(--text-muted)",
        success: "var(--success)",
        warning: "var(--warning)",
        danger: "var(--danger)",
      },
      borderRadius: {
        card: "12px",
        input: "12px",
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "-apple-system", "sans-serif"],
      },
    },
  },
  plugins: [],
};
