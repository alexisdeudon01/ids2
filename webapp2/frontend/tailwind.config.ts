import type { Config } from "tailwindcss";

export default {
  darkMode: ["class"],
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        glass: "rgba(15, 23, 42, 0.6)",
      },
    },
  },
  plugins: [],
} satisfies Config;
