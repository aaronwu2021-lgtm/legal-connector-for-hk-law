// One attempt per call, including POST. Only a user action starts a retry.
function requestError(code, message, cause) {
  const error = new Error(message, cause ? {cause} : undefined);
  error.code = code;
  return error;
}

export function createApiClient({base = '/api', fetcher = (...args) => fetch(...args), timeoutMs = 15000, onStatus = () => {}} = {}) {
  let sequence = 0, lastSettled = 0, state = 'idle';
  const publish = (next, details = {}) => { state = next; onStatus({state, ...details}); };
  const settle = (request, next, details) => {
    // Concurrent metadata loads may fail while another is still pending.
    // Report actual completions, but never overwrite a newer completed result.
    if (request < lastSettled) return;
    lastSettled = request;
    publish(next, details);
  };
  return async function request(path, options = {}) {
    const {signal, ...init} = options;
    if (signal?.aborted) throw new DOMException('请求已取消', 'AbortError');
    const current = ++sequence;
    if (state !== 'online' && state !== 'connecting') publish('connecting');
    const controller = new AbortController();
    let timer, cancel, timedOut = false;
    const interruption = new Promise((_, reject) => {
      cancel = () => {
        controller.abort();
        reject(new DOMException('请求已取消', 'AbortError'));
      };
      signal?.addEventListener('abort', cancel, {once: true});
      timer = setTimeout(() => {
        timedOut = true;
        controller.abort();
        reject(requestError('timeout', '请求超时。请确认数据服务正在运行，然后重试。'));
      }, timeoutMs);
    });
    try {
      // Race the complete JSON read as well as fetch: headers alone do not
      // complete the request, and a transport may ignore abort signals.
      const result = await Promise.race([
        (async () => {
          const response = await fetcher(base + path, {...init, signal: controller.signal});
          let data;
          try { data = await response.json(); }
          catch (cause) { throw requestError('invalid-response', '数据服务返回了无法读取的内容，请重试。', cause); }
          return {ok: response.ok, status: response.status, data};
        })(),
        interruption,
      ]);
      settle(current, result.ok ? 'online' : 'error', {status: result.status});
      return result;
    } catch (cause) {
      if (signal?.aborted) throw new DOMException('请求已取消', 'AbortError');
      const error = timedOut ? requestError('timeout', '请求超时。请确认数据服务正在运行，然后重试。')
        : cause?.code === 'timeout' || cause?.code === 'invalid-response'
        ? cause : requestError('network', '无法连接数据服务。请确认服务正在运行，然后重试。', cause);
      settle(current, error.code === 'invalid-response' ? 'error' : 'offline', {error});
      throw error;
    } finally {
      clearTimeout(timer);
      signal?.removeEventListener('abort', cancel);
    }
  };
}

// Failed initial data does not poison the page: a later explicit call can
// load again. Superseded initializations never commit or paint errors.
export function createBootstrap({load, commit, onLoading, onError, onReady}) {
  let sequence = 0, controller;
  return async function bootstrap() {
    const request = ++sequence;
    controller?.abort();
    controller = new AbortController();
    onLoading();
    try {
      const data = await load(controller.signal);
      if (request !== sequence) return;
      commit(data);
      await onReady(data);
    } catch (error) {
      if (request === sequence) {
        controller.abort();
        onError(error);
      }
    }
  };
}
