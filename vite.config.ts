import adapter from "@sveltejs/adapter-static";
import { sveltekit } from "@sveltejs/kit/vite";
import tailwindcss from "@tailwindcss/vite";
import { defineConfig } from "vite";

// SvelteKit 3 takes its configuration from the Vite plugin, not svelte.config.js.
// Static output because server/web.py owns routing and the API: the SPA is emitted
// to web/dist and served as files.
export default defineConfig({
  plugins: [
    tailwindcss(),
    sveltekit({
      adapter: adapter({
        pages: "web/dist",
        assets: "web/dist",
        fallback: "index.html",
        precompress: false,
        strict: false,
      }),
      // SvelteKit 3 warns that config.alias is deprecated in favour of subpath
      // imports. Keeping it is deliberate: migrating every $lib import is a
      // mechanical change that adds risk with no user-visible benefit, and the
      // warning does not fail CI.
      alias: {
        $lib: "src/lib",
      },
    }),
  ],
  // `npm run dev` serves the UI on 5173 while the Python server owns the API on 8649.
  // Without this, every /api call is a 404 in dev mode and a contributor cannot see
  // real data without building first.
  server: {
    proxy: {
      "/api": {
        // Read through globalThis so this file type-checks without @types/node,
        // which the project does not otherwise need.
        target:
          (globalThis as { process?: { env?: Record<string, string | undefined> } })
            .process?.env?.LAYA_API ?? "http://127.0.0.1:8649",
        changeOrigin: false,
      },
    },
  },
});
