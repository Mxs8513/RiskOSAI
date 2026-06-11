import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: "#FAFAFA",
        card: "#FFFFFF",
        subtle: "#F4F4F5",
        border: { DEFAULT: "#E4E4E7", strong: "#D4D4D8" },
        ink: "#09090B",
        muted: "#71717A",
        faint: "#A1A1AA",
        primary: { DEFAULT: "#4F46E5", hover: "#4338CA", soft: "#EEF2FF", border: "#C7D2FE" },
        success: { DEFAULT: "#16A34A", soft: "#F0FDF4", border: "#BBF7D0" },
        warn: { DEFAULT: "#D97706", soft: "#FFFBEB", border: "#FDE68A" },
        danger: { DEFAULT: "#DC2626", soft: "#FEF2F2", border: "#FECACA" },
        info: { DEFAULT: "#2563EB", soft: "#EFF6FF", border: "#BFDBFE" },
      },
      fontFamily: {
        sans: ["var(--font-geist-sans)", "ui-sans-serif", "system-ui", "sans-serif"],
        mono: ["var(--font-geist-mono)", "ui-monospace", "SFMono-Regular", "monospace"],
      },
      fontSize: { xxs: ["11px", "16px"] },
      boxShadow: {
        card: "0 0 0 1px rgba(9,9,11,0.03), 0 1px 2px rgba(9,9,11,0.05)",
        lift: "0 0 0 1px rgba(9,9,11,0.04), 0 8px 24px -8px rgba(9,9,11,0.14)",
        pop: "0 0 0 1px rgba(9,9,11,0.05), 0 16px 48px -12px rgba(9,9,11,0.22)",
        "focus-primary": "0 0 0 3px rgba(79,70,229,0.25)",
      },
      keyframes: {
        "fade-up": { from: { opacity: "0", transform: "translateY(6px)" }, to: { opacity: "1", transform: "translateY(0)" } },
        "fade-in": { from: { opacity: "0" }, to: { opacity: "1" } },
        "slide-in-right": { from: { opacity: "0", transform: "translateX(24px)" }, to: { opacity: "1", transform: "translateX(0)" } },
        "toast-in": { from: { opacity: "0", transform: "translate(-50%, 12px) scale(0.97)" }, to: { opacity: "1", transform: "translate(-50%, 0) scale(1)" } },
        shimmer: { from: { backgroundPosition: "200% 0" }, to: { backgroundPosition: "-200% 0" } },
        "pulse-ring": {
          "0%": { boxShadow: "0 0 0 0 rgba(22,163,74,0.45)" },
          "70%": { boxShadow: "0 0 0 5px rgba(22,163,74,0)" },
          "100%": { boxShadow: "0 0 0 0 rgba(22,163,74,0)" },
        },
        "grow-x": { from: { transform: "scaleX(0)" }, to: { transform: "scaleX(1)" } },
      },
      animation: {
        "fade-up": "fade-up 0.35s cubic-bezier(0.21,1.02,0.73,1) both",
        "fade-in": "fade-in 0.2s ease-out both",
        "slide-in-right": "slide-in-right 0.32s cubic-bezier(0.21,1.02,0.73,1) both",
        "toast-in": "toast-in 0.28s cubic-bezier(0.21,1.02,0.73,1) both",
        shimmer: "shimmer 1.6s linear infinite",
        "pulse-ring": "pulse-ring 1.8s cubic-bezier(0.4,0,0.6,1) infinite",
        "grow-x": "grow-x 0.6s cubic-bezier(0.21,1.02,0.73,1) both",
      },
    },
  },
  plugins: [],
};
export default config;
