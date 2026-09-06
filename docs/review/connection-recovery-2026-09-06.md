# Page connection and retry repair — 2026-09-06

The parent agent reproduced a stopped local preview server: requests to port 8918 were refused, the page displayed a loading failure, and its header still said `live · 745 posts`. Restoring the background server is handled separately by the parent agent.

## Page changes

- Initial metadata loading can be retried from a visible button. It commits taxonomy, elements and statistics only after all three requests succeed. A newer initialization cancels and supersedes the previous one.
- Page-load errors now offer **重试加载**. Corpus search, case lists and historical-date results can retry without changing their conditions. Existing navigation ownership and scoring-response guards remain in place.
- A shared JSON request helper bounds both receiving the response and reading its body to **15 seconds**. This leaves room for the server's 10-second live-citation deadline. Network loss, timeout, invalid JSON and non-success HTTP responses update the header. It says **最近请求成功**, rather than implying continuous health monitoring.
- All existing direct POST paths use the same bounded helper. Each call sends once. No automatic retry, polling, or replay of scoring/proposal submissions was added. After startup, **检查连接** sends only a health GET and preserves the current page and inputs.
- The proposal button is disabled during its request; late output is limited to its original connected container. The native `hidden` display rule is restored so the header's connection-check button is actually hidden after success, despite the chip display style.

The shared status ordering reports completed requests by their start sequence: an old completion cannot overwrite an already completed newer request. A pending newer request does not conceal an actual failure from another concurrent metadata request. Caller-initiated cancellation does not report a lost connection.

## Scope and verification

Changed `server/public/index.html`; added `server/public/connection.js`, `server/test/connection-recovery.test.mjs`, and this note. No data, generated module, API implementation, model, external service, or existing test was changed by this subtask. No preview service was started or stopped by this subtask.

Before editing, the exact index bytes were saved at `.git/codex-review/2026-09-06-connection-before/server/public/index.html`, SHA-256 `d44564db6dc33091cb9a2e85e9d022f91d23fb920beba451690ca5fb1fc8f88c`. Its LF line endings and zero NUL bytes were preserved. The API file still contains its pre-existing two NUL bytes.

Independent connection tests passed **24/24**: 21 helper cases and three VM cases executing the real page code. They cover fetch/body stalls, cancellation, old-result ordering, manual startup recovery, same-page retry, and health checks that do not replay failed POSTs. All requests use local adapters; no real network is used.

The final combined command `node --test "test/**/*.test.mjs"`, from `server`, passed **243/243** on **Node 24.19.0**. This includes the earlier 214 tests, the parent's five preview-start tests, and the 24 new connection tests. Syntax and whitespace checks passed. The parent agent separately owns actual browser stop/restart/retry acceptance; these offline results do not substitute for that browser check.

The page cannot itself restart a stopped operating-system process. If the server cannot serve the HTML at all, the browser's own connection-error page appears; the launcher must restore the service first. This repair makes an already loaded page's failures bounded, truthful, and recoverable through explicit user actions.
