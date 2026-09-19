import colors from "tailwindcss/colors";

/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        // Single accent. Kept as indigo/violet (not teal) so "action" never
        // reads as the teal/emerald used for APPROVED / VERIFIED status badges.
        brand: colors.indigo,
        // Dark-only surface scale (deep navy, not pure black).
        canvas: "#0B1020",
        surface: "#111833",
        raised: "#172040",
        // Text scale — ink/muted/faint all keep >= 4.5:1 on canvas and surface.
        ink: "#E6E9F5",
        muted: "#9AA3BF",
        faint: "#7C86A6",
      },
      fontFamily: {
        sans: [
          "Inter var",
          "Inter",
          "ui-sans-serif",
          "system-ui",
          "-apple-system",
          "Segoe UI",
          "Roboto",
          "Helvetica Neue",
          "Arial",
          "sans-serif",
        ],
        mono: [
          "JetBrains Mono",
          "ui-monospace",
          "SFMono-Regular",
          "Menlo",
          "Consolas",
          "monospace",
        ],
      },
      boxShadow: {
        card: "0 1px 0 0 rgb(255 255 255 / 0.03) inset",
        glow: "0 0 0 1px rgb(129 140 248 / 0.35), 0 0 24px -2px rgb(99 102 241 / 0.45)",
        "glow-lg": "0 0 0 1px rgb(129 140 248 / 0.5), 0 0 36px 0 rgb(99 102 241 / 0.55)",
        "card-hover": "0 0 0 1px rgb(129 140 248 / 0.25), 0 8px 32px -12px rgb(99 102 241 / 0.35)",
      },
      keyframes: {
        "fade-up": {
          from: { opacity: "0", transform: "translateY(12px)" },
          to: { opacity: "1", transform: "translateY(0)" },
        },
        "fade-in": {
          from: { opacity: "0" },
          to: { opacity: "1" },
        },
        shimmer: {
          "100%": { transform: "translateX(100%)" },
        },
        drift: {
          "0%, 100%": { transform: "translate3d(0,0,0)" },
          "50%": { transform: "translate3d(2%, -3%, 0)" },
        },
      },
      animation: {
        "fade-up": "fade-up 500ms cubic-bezier(0.22, 1, 0.36, 1) both",
        "fade-in": "fade-in 300ms ease-out both",
        shimmer: "shimmer 1.6s infinite",
        drift: "drift 18s ease-in-out infinite",
      },
    },
  },
  plugins: [],
};
