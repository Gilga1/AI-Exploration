/**
 * Local stand-in for the Claude artifact inject bridge.
 * Real Claude injects window.claude + window.storage and patches fetch.
 * This file lets the gallery run outside claude.ai with mock data.
 */
(function installMockClaudeBridge(global) {
  if (global.__CLAUDE_ARTIFACT_BRIDGE__) return;
  global.__CLAUDE_ARTIFACT_BRIDGE__ = "mock";

  const personal = new Map();
  const shared = new Map();

  function pool(isShared) {
    return isShared ? shared : personal;
  }

  function result(type, key, isShared, value) {
    const row = { "@type": type, key, shared: !!isShared };
    if (value !== undefined) row.value = value;
    return row;
  }

  global.storage = {
    async get(key, isShared = false) {
      const p = pool(isShared);
      if (!p.has(key)) {
        return Promise.reject(new Error(`storage key not found: ${key}`));
      }
      const value = p.get(key);
      return result("storage_get_result", key, isShared, value);
    },
    async set(key, value, isShared = false) {
      const serialized =
        typeof value === "string" ? value : JSON.stringify(value);
      pool(isShared).set(key, serialized);
      return result("storage_set_result", key, isShared, serialized);
    },
    async delete(key, isShared = false) {
      const p = pool(isShared);
      if (!p.has(key)) {
        return Promise.reject(new Error(`storage key not found: ${key}`));
      }
      p.delete(key);
      return result("storage_delete_result", key, isShared);
    },
    async list(prefix = "", isShared = false) {
      const keys = [...pool(isShared).keys()].filter((k) =>
        k.startsWith(prefix || "")
      );
      return { "@type": "storage_list_result", shared: !!isShared, keys, prefix };
    },
  };

  function mockComplete(input) {
    const prompt =
      typeof input === "string"
        ? input
        : JSON.stringify(input?.messages ?? input);

    // Deterministic mock “AI” for local preview — not a real model.
    let focus = "fleet";
    if (/V-\d+/i.test(prompt)) {
      const m = prompt.match(/V-\d+/i);
      focus = m[0].toUpperCase();
    }

    const historyHint = /conversation history/i.test(prompt)
      ? " (used full history you serialized)"
      : "";

    if (typeof input === "object" && input?.messages) {
      const last = [...input.messages].reverse().find((m) => m.role === "user");
      const text =
        typeof last?.content === "string"
          ? last.content
          : JSON.stringify(last?.content ?? "");
      return JSON.stringify({
        response: `Mock coach on ${focus}: ${text.slice(0, 120)}${historyHint}`,
        sentiment: "focused",
        mock: true,
      });
    }

    return JSON.stringify({
      response: `Mock coach summary for ${focus}${historyHint}. Check delay reasons and yard capacity before reassigning.`,
      sentiment: "neutral",
      mock: true,
    });
  }

  global.claude = {
    async complete(input) {
      await new Promise((r) => setTimeout(r, 280));
      return mockComplete(input);
    },
  };

  const realFetch = global.fetch.bind(global);
  global.fetch = async function patchedFetch(resource, init) {
    const url = typeof resource === "string" ? resource : resource.url;
    if (url && url.includes("api.anthropic.com") && url.includes("/v1/messages")) {
      await new Promise((r) => setTimeout(r, 320));
      let body = {};
      try {
        body = JSON.parse(init?.body || "{}");
      } catch {
        body = {};
      }
      const text = mockComplete(body);
      return new Response(
        JSON.stringify({
          id: "msg_mock_local",
          type: "message",
          role: "assistant",
          model: body.model || "mock-haiku",
          content: [{ type: "text", text }],
          stop_reason: "end_turn",
          usage: { input_tokens: 42, output_tokens: 64 },
        }),
        { status: 200, headers: { "Content-Type": "application/json" } }
      );
    }
    return realFetch(resource, init);
  };

  console.info(
    "[mock-bridge] window.claude + window.storage + Anthropic fetch proxy installed"
  );
})(typeof window !== "undefined" ? window : globalThis);
