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
});
