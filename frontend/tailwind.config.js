/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#17212b",
        panel: "#f7f9fb",
        line: "#d8e0e8",
      },
    },
  },
  plugins: [],
};
