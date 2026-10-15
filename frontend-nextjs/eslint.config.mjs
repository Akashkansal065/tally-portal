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
    files: ["src/console/**/*.{ts,tsx}", "src/app/(console)/**/*.{ts,tsx}"],
    rules: {
      "no-restricted-imports": [
        "error",
        {
          patterns: [
            {
              group: ["@/context/*"],
              message: "Console must maintain its own state and never import customer app context.",
            },
            {
              group: ["@/components/*", "!@/components/ui/*", "!@/components/ThemeProvider"],
              message: "Console may only import shared UI primitives (@/components/ui/*).",
            },
          ],
        },
      ],
    },
  },
  {
    files: ["src/**/*.{ts,tsx}"],
    ignores: ["src/console/**/*.{ts,tsx}", "src/app/(console)/**/*.{ts,tsx}"],
    rules: {
      "no-restricted-imports": [
        "error",
        {
          patterns: [
            {
              group: ["@/console/*"],
              message: "Customer app must never import console code directly.",
            },
          ],
        },
      ],
    },
  },
]);

export default eslintConfig;
