// Connects to the FastAPI /ws/events endpoint. Reconnects with backoff so
// a dropped connection (backend restart, network blip) recovers without a
// page refresh, per the "WebSockets reconnect" requirement.
const IndraSocket = (() => {
  let socket = null;
  let backoff = 1000;
  const listeners = new Set();

  function wsUrl() {
    const httpBase = API_BASE || window.location.origin;
    const u = new URL(httpBase);
    u.protocol = u.protocol === "https:" ? "wss:" : "ws:";
    u.pathname = "/ws/events";
    return u.toString();
  }

  function connect() {
    try {
      socket = new WebSocket(wsUrl());
    } catch (e) {
      scheduleReconnect();
      return;
    }
    socket.onopen = () => { backoff = 1000; };
    socket.onmessage = (evt) => {
      let msg;
      try { msg = JSON.parse(evt.data); } catch { return; }
      listeners.forEach((fn) => fn(msg));
    };
    socket.onclose = scheduleReconnect;
    socket.onerror = () => socket && socket.close();
  }

  function scheduleReconnect() {
    setTimeout(connect, backoff);
    backoff = Math.min(backoff * 1.6, 15000);
  }

  function on(fn) {
    listeners.add(fn);
    return () => listeners.delete(fn);
  }

  connect();
  return { on };
})();
