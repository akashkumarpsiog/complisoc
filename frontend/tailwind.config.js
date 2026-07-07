/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#0f172a",
        panel: "#f8fafc",
        line: "#e2e8f0",
        brand: {
          50: "#eef4ff",
          100: "#dbe6fe",
          200: "#bfd2fe",
          500: "#3b6df6",
          600: "#2f59e0",
          700: "#2647b8",
          800: "#1e3a8a",
        },
      },
      borderRadius: {
        xl: "0.875rem",
      },
    },
  },
  plugins: [],
};
