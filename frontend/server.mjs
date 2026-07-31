import { createServer } from "node:http";
import { readFile } from "node:fs/promises";
import { extname, join, normalize } from "node:path";

const port = Number(process.env.PORT || 5173);
const dist = join(process.cwd(), "dist");
const types = {
  ".html": "text/html; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".svg": "image/svg+xml",
  ".png": "image/png",
  ".ico": "image/x-icon"
};

createServer(async (req, res) => {
  try {
    const url = new URL(req.url || "/", `http://${req.headers.host}`);
    const requested = normalize(url.pathname === "/" ? "/index.html" : url.pathname);
    let filePath = join(dist, requested);
    if (!filePath.startsWith(dist)) {
      res.writeHead(403);
      res.end("Forbidden");
      return;
    }
    try {
      const body = await readFile(filePath);
      res.writeHead(200, { "Content-Type": types[extname(filePath)] || "application/octet-stream" });
      res.end(body);
    } catch {
      const body = await readFile(join(dist, "index.html"));
      res.writeHead(200, { "Content-Type": types[".html"] });
      res.end(body);
    }
  } catch (error) {
    res.writeHead(500);
    res.end(String(error));
  }
}).listen(port, "0.0.0.0", () => {
  console.log(`Smart Rental frontend running at http://0.0.0.0:${port}`);
});
