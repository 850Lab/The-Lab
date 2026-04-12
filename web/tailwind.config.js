/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        lab: {
          /** Charcoal / terminal black — neutral, no blue in chrome */
          bg: "#0a0a0a",
          surface: "#111111",
          elevated: "#1a1a1a",
          text: "#f4f4f5",
          muted: "#a1a1aa",
          subtle: "#71717a",
          accent: "#3B82F6",
        },
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "-apple-system", "BlinkMacSystemFont", "Segoe UI", "Roboto", "sans-serif"],
        /** Headings — Inter Tight (key is `heading` so utility is `font-heading`; `display` conflicts with CSS font-display) */
        heading: ['"Inter Tight"', "Inter", "system-ui", "sans-serif"],
      },
    },
  },
  plugins: [],
};
