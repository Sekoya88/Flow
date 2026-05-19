import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";

const eslintConfig = defineConfig([
  ...nextVitals,
  ...nextTs,
  // Override default ignores of eslint-config-next.
  globalIgnores([
    // Default ignores of eslint-config-next:
    ".next/**",
    "out/**",
    "build/**",
    "next-env.d.ts",
  ]),
  {
    rules: {
      // Common async data-fetching pattern — not a bug, just a perf hint
      "react-hooks/set-state-in-effect": "warn",
      // Too strict for a fast-moving codebase
      "@typescript-eslint/no-explicit-any": "warn",
      // Cosmetic JSX escaping — not a functional issue
      "react/no-unescaped-entities": "off",
    },
  },
]);

export default eslintConfig;
