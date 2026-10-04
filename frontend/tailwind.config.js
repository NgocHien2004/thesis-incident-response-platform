/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        primary: {
          50:  "#eef2ff",
          100: "#e0e7ff",
          500: "#6366f1",
          600: "#4f46e5",
          700: "#4338ca",
        },
        danger:  { 500: "#ef4444", 100: "#fee2e2" },
        warning: { 500: "#f59e0b", 100: "#fef3c7" },
        success: { 500: "#10b981", 100: "#d1fae5" },
        gray:    { 50: "#f9fafb", 100: "#f3f4f6", 200: "#e5e7eb", 700: "#374151", 800: "#1f2937", 900: "#111827" },
      }
    }
  },
  plugins: [],
}