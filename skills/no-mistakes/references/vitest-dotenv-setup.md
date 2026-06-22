# Vitest dotenv Setup

## Problem
Vitest has no built-in `.env` loading (`process.env` is empty unless explicitly set). Integration tests that need `MONGODB_URI` or similar will fail with "not set."

## Fix

### 1. Install dotenv
```bash
npm install dotenv
```

### 2. Create setup file
`tests/setup.ts`:
```ts
import "dotenv/config";
```

### 3. Wire into vitest config
`vitest.config.ts`:
```ts
import { defineConfig } from "vitest/config";
import path from "path";

export default defineConfig({
  test: {
    environment: "node",
    include: ["tests/**/*.test.ts"],
    setupFiles: ["tests/setup.ts"],
  },
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
});
```

## Verification
```bash
npx vitest run tests/team-invites-mongo.test.ts
# Should pass with MONGODB_URI loaded from .env
```

## Prerequisites
- `.env` file must exist at project root with `MONGODB_URI=mongodb://...`
- MongoDB must be running (Docker: `docker ps | grep mongo`)
- `package.json` must have `dotenv` in dependencies
