import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Emit a self-contained server bundle (.next/standalone/server.js) with
  // only the node_modules it actually traces. The Docker runtime stage
  // copies that bundle instead of running `npm ci` again — small image,
  // fast cold start. See apps/web/Dockerfile.
  output: "standalone",

  // Pin the file-tracing root to THIS directory. Without it, Next walks up
  // looking for a lockfile and (because there are stray lockfiles higher in
  // the tree) mis-roots the standalone bundle, nesting server.js many dirs
  // deep instead of at .next/standalone/server.js. This app is a
  // self-contained npm project, so its own dir is the correct root.
  outputFileTracingRoot: import.meta.dirname,
};

export default nextConfig;
