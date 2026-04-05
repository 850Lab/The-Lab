import path from "node:path";
import type { ServerResponse } from "node:http";
import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  // Default matches scripts/replit_deployment_entry.sh (uvicorn :5000). If you use
  // `uvicorn ... --port 8000`, set WORKFLOW_API_PROXY_TARGET=http://127.0.0.1:8000 in web/.env.local
  const proxyTarget =
    env.WORKFLOW_API_PROXY_TARGET?.trim() ||
    env.VITE_WORKFLOW_API_PROXY_TARGET?.trim() ||
    "http://127.0.0.1:5000";

  const workflowApiProxy = {
    target: proxyTarget,
    changeOrigin: true,
    timeout: 180_000,
    proxyTimeout: 180_000,
    rewrite: (p: string) => p.replace(/^\/workflow-api/, ""),
    /**
     * Default http-proxy behavior on ECONNREFUSED is HTTP 500 + empty body — the demo UI
     * then shows “empty response”. Return JSON so operators see a clear fix.
     */
    configure(proxy) {
      proxy.on("error", (err, _req, res) => {
        const out = res as ServerResponse | undefined;
        if (!out?.writeHead || out.headersSent) {
          return;
        }
        const code = (err as NodeJS.ErrnoException)?.code;
        const messageSafe = [
          `Workflow API proxy could not reach ${proxyTarget}.`,
          code === "ECONNREFUSED"
            ? "Start the workflow server (e.g. python -m uvicorn api.workflow_app:app --host 127.0.0.1 --port 5000) or set WORKFLOW_API_PROXY_TARGET in web/.env.local to the URL where it is running."
            : String((err as Error)?.message || err),
        ].join(" ");
        out.writeHead(502, { "Content-Type": "application/json" });
        out.end(
          JSON.stringify({
            detail: {
              code: "WORKFLOW_API_PROXY_UNREACHABLE",
              messageSafe,
            },
          }),
        );
      });
    },
  };

  return {
    plugins: [react()],
    resolve: {
      alias: { "@": path.resolve(__dirname, "src") },
    },
    server: {
      host: "0.0.0.0",
      port: 5173,
      strictPort: false,
      proxy: {
        "/workflow-api": workflowApiProxy,
      },
    },
    preview: {
      proxy: {
        "/workflow-api": workflowApiProxy,
      },
    },
  };
});
