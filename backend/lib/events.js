// Event bus — the cross-device / vision event channel. The blueprint specifies
// WebSocket; to stay dependency-free we expose the same event stream over
// Server-Sent Events (SSE) plus a polled ring buffer. Both are real and live.

const subscribers = new Set(); // res objects for SSE
const ring = []; // recent events for polling clients
let seq = 0;

export function emit(event) {
  const record = { seq: ++seq, ts: new Date().toISOString(), ...event };
  ring.push(record);
  if (ring.length > 500) ring.splice(0, ring.length - 500);
  for (const res of subscribers) {
    try {
      res.write(`data: ${JSON.stringify(record)}\n\n`);
    } catch {
      subscribers.delete(res);
    }
  }
  return record;
}

export function recent({ since = 0, limit = 100 } = {}) {
  return ring.filter((e) => e.seq > since).slice(-limit);
}

// Attach an SSE response. Returns a detach function.
export function subscribe(res) {
  res.writeHead(200, {
    "Content-Type": "text/event-stream",
    "Cache-Control": "no-cache",
    Connection: "keep-alive",
    "Access-Control-Allow-Origin": "*",
  });
  res.write(`retry: 3000\n\n`);
  subscribers.add(res);
  return () => subscribers.delete(res);
}

export function _resetEventsForTests() {
  subscribers.clear();
  ring.length = 0;
  seq = 0;
}
