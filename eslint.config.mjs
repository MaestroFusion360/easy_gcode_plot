import js from "@eslint/js";
import globals from "globals";

export default [
  {
    files: ["docs/*.js", "scripts/landing/*.mjs", "*.config.mjs"],
    rules: js.configs.recommended.rules,
    languageOptions: { ecmaVersion: "latest" },
  },
  { files: ["docs/*.js"], languageOptions: { globals: globals.browser } },
  {
    files: ["scripts/landing/*.mjs", "*.config.mjs"],
    languageOptions: { globals: globals.node },
  },
];
