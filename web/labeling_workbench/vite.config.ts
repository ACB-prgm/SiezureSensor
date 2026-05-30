import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { spawn, type ChildProcessWithoutNullStreams } from "node:child_process";
import { existsSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { loadEnv, type Plugin } from "vite";

type ControlStatus = {
  apiBaseUrl: string;
  apiReachable: boolean;
  managed: boolean;
  pid: number | null;
  message: string;
  logs: string[];
};

const configDir = dirname(fileURLToPath(import.meta.url));
const repoRoot = resolve(configDir, "../..");
const serverDir = resolve(repoRoot, "server");
const serverPython = resolve(serverDir, ".venv/bin/python");

let apiProcess: ChildProcessWithoutNullStreams | null = null;
const apiLogs: string[] = [];

function recordApiLog(chunk: Buffer): void {
  const lines = chunk
    .toString()
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean);
  apiLogs.push(...lines);
  apiLogs.splice(0, Math.max(0, apiLogs.length - 80));
}

function jsonResponse(response: { statusCode: number; setHeader: (name: string, value: string) => void; end: (body: string) => void }, statusCode: number, body: unknown): void {
  response.statusCode = statusCode;
  response.setHeader("Content-Type", "application/json");
  response.end(JSON.stringify(body));
}

async function probeApi(apiBaseUrl: string, timeoutMs = 1200): Promise<boolean> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(`${apiBaseUrl}/health`, { signal: controller.signal });
    return response.ok;
  } catch {
    return false;
  } finally {
    clearTimeout(timeout);
  }
}

async function waitForApi(apiBaseUrl: string, timeoutMs = 8000): Promise<boolean> {
  const startedAt = Date.now();
  while (Date.now() - startedAt < timeoutMs) {
    if (await probeApi(apiBaseUrl, 700)) {
      return true;
    }
    await new Promise((resolveDelay) => setTimeout(resolveDelay, 350));
  }
  return false;
}

async function buildControlStatus(apiBaseUrl: string): Promise<ControlStatus> {
  const apiReachable = await probeApi(apiBaseUrl);
  const managed = apiProcess !== null && apiProcess.exitCode === null;
  return {
    apiBaseUrl,
    apiReachable,
    managed,
    pid: managed ? apiProcess?.pid ?? null : null,
    message: apiReachable ? "FastAPI is reachable." : "FastAPI is not reachable.",
    logs: apiLogs.slice(-12),
  };
}

function apiControlPlugin(apiBaseUrl: string): Plugin {
  return {
    name: "seizure-sensor-api-control",
    configureServer(server) {
      server.middlewares.use("/__dev/api", async (request, response, next) => {
        const path = request.url?.split("?")[0] ?? "/";

        if (request.method === "GET" && path === "/status") {
          jsonResponse(response, 200, await buildControlStatus(apiBaseUrl));
          return;
        }

        if (request.method === "POST" && path === "/start") {
          if (await probeApi(apiBaseUrl)) {
            jsonResponse(response, 200, await buildControlStatus(apiBaseUrl));
            return;
          }

          if (apiProcess && apiProcess.exitCode === null) {
            jsonResponse(response, 202, await buildControlStatus(apiBaseUrl));
            return;
          }

          const pythonCommand = existsSync(serverPython) ? serverPython : "python3";
          apiLogs.length = 0;
          apiProcess = spawn(
            pythonCommand,
            ["-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"],
            {
              cwd: serverDir,
              env: process.env,
              stdio: "pipe",
            },
          );
          apiProcess.stdout.on("data", recordApiLog);
          apiProcess.stderr.on("data", recordApiLog);
          apiProcess.on("exit", (code, signal) => {
            apiLogs.push(`FastAPI exited with code ${code ?? "null"} signal ${signal ?? "null"}`);
            apiProcess = null;
          });

          const started = await waitForApi(apiBaseUrl);
          jsonResponse(response, started ? 200 : 500, {
            ...(await buildControlStatus(apiBaseUrl)),
            message: started ? "FastAPI started." : "FastAPI failed to start before timeout.",
          });
          return;
        }

        if (request.method === "POST" && path === "/stop") {
          if (!apiProcess || apiProcess.exitCode !== null) {
            jsonResponse(response, 409, {
              ...(await buildControlStatus(apiBaseUrl)),
              message: "FastAPI is not managed by this dashboard process. Stop it from the terminal if it was started elsewhere.",
            });
            return;
          }

          apiProcess.kill("SIGTERM");
          await new Promise((resolveDelay) => setTimeout(resolveDelay, 700));
          jsonResponse(response, 200, {
            ...(await buildControlStatus(apiBaseUrl)),
            message: "FastAPI stop requested.",
          });
          return;
        }

        next();
      });
    },
  };
}

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  const apiBaseUrl = env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";

  return {
    plugins: [react(), apiControlPlugin(apiBaseUrl)],
    server: {
      host: "0.0.0.0",
      port: 5173,
    },
  };
});
