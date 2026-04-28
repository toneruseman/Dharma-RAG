import { dirname } from "node:path";
import { fileURLToPath } from "node:url";
import type { NextConfig } from "next";

// Anchor Turbopack's workspace-root inference at the repo root rather
// than letting it walk up to the user home and find some unrelated
// lockfile. The repo root is the parent of `web/`.
const repoRoot = dirname(dirname(fileURLToPath(import.meta.url)));

const nextConfig: NextConfig = {
  turbopack: {
    root: repoRoot,
  },
};

export default nextConfig;
