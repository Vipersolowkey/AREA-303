import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: ["class"],
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./lib/**/*.{ts,tsx}",
  ],
  theme: {
    container: {
      center: true,
      padding: "2rem",
      screens: { "2xl": "1440px" },
    },
    extend: {
      colors: {
        bg: "hsl(var(--bg))",
        "bg-alt": "hsl(var(--bg-alt))",
        surface: "hsl(var(--surface))",
        "surface-2": "hsl(var(--surface-2))",
        "surface-3": "hsl(var(--surface-3))",
        text: "hsl(var(--text))",
        "text-muted": "hsl(var(--text-muted))",
        "text-dim": "hsl(var(--text-dim))",
        border: "hsl(var(--border))",
        "border-strong": "hsl(var(--border-strong))",
        accent: {
          DEFAULT: "hsl(var(--accent))",
          hover: "hsl(var(--accent-hover))",
          deep: "hsl(var(--accent-deep))",
        },
        "accent-2": {
          DEFAULT: "hsl(var(--accent-2))",
          hover: "hsl(var(--accent-2-hover, var(--accent-2)))",
        },
        success: "hsl(var(--success))",
        warning: "hsl(var(--warning))",
        danger: "hsl(var(--danger))",
        info: "hsl(var(--info))",
        series: {
          1: "hsl(var(--series-1))",
          2: "hsl(var(--series-2))",
          3: "hsl(var(--series-3))",
          4: "hsl(var(--series-4))",
          5: "hsl(var(--series-5))",
        },
      },
      borderRadius: {
        lg: "var(--radius)",
        md: "calc(var(--radius) - 2px)",
        sm: "calc(var(--radius) - 4px)",
      },
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "ui-monospace", "SFMono-Regular", "Menlo", "monospace"],
      },
      fontSize: {
        "2xs": ["11px", { lineHeight: "1.4", letterSpacing: "0.04em" }],
        xs: ["12px", { lineHeight: "1.4" }],
        sm: ["13px", { lineHeight: "1.5" }],
        base: ["14px", { lineHeight: "1.5" }],
        lg: ["16px", { lineHeight: "1.5" }],
        xl: ["18px", { lineHeight: "1.4" }],
        "2xl": ["22px", { lineHeight: "1.3" }],
        "3xl": ["28px", { lineHeight: "1.2" }],
        "4xl": ["36px", { lineHeight: "1.2", letterSpacing: "-0.01em" }],
        "5xl": ["48px", { lineHeight: "1.1", letterSpacing: "-0.02em" }],
        // Landing-page display sizes.
        "6xl": ["60px", { lineHeight: "1.05", letterSpacing: "-0.03em" }],
        "7xl": ["72px", { lineHeight: "1.0", letterSpacing: "-0.03em" }],
      },
      keyframes: {
        "accordion-down": {
          from: { height: "0" },
          to: { height: "var(--radix-accordion-content-height)" },
        },
        "accordion-up": {
          from: { height: "var(--radix-accordion-content-height)" },
          to: { height: "0" },
        },
        "caret-blink": {
          "0%,50%,100%": { opacity: "1" },
          "25%,75%": { opacity: "0" },
        },
      },
      animation: {
        "accordion-down": "accordion-down 0.2s ease-out",
        "accordion-up": "accordion-up 0.2s ease-out",
        "caret-blink": "caret-blink 1.2s ease-in-out infinite",
      },
    },
  },
  plugins: [require("tailwindcss-animate")],
};

export default config;