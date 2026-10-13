const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const html = fs.readFileSync('app/static/index.html', 'utf8');
function element(value = '') {
  return { value, events: {}, children: [], dataset: {},
    addEventListener(name, callback) { this.events[name] = callback; },
    replaceChildren(...items) { this.children = items; },
    append(...items) { this.children.push(...items); },
    focus() { this.focused = true; },
  };
}
test('質問例は実際のclick handlerで入力だけを行い、通信・送信しない', async () => {
  const buttons = [...html.matchAll(/<button type="button" data-prompt="([^"]+)">/g)]
    .map((match) => Object.assign(element(), { dataset: { prompt: match[1] } }));
  assert.equal(buttons.length, 3);
  const elements = new Map();
  const get = (selector) => {
    if (!elements.has(selector)) elements.set(selector, element());
    return elements.get(selector);
  };
  let requests = 0;
  const context = { document: { querySelector: get, querySelectorAll: () => buttons,
      createElement: () => element() },
    window: { addEventListener() {} },
    fetch: async () => { requests++; return { ok: true, json: async () => [] }; },
  };
  vm.runInNewContext(fs.readFileSync('app/static/app.js', 'utf8'), context);
  // Existing page startup fetches document status; clicks must add no requests.
  await new Promise(setImmediate);
  const baseline = requests;
  get('#message').value = 'previous draft';
  for (const button of buttons) {
    await button.events.click();
    assert.equal(get('#message').value, button.dataset.prompt);
    assert.equal(get('#message').focused, true);
    assert.equal(requests, baseline);
  }
  assert.ok(buttons[0].dataset.prompt.includes('有給残日数'));
  assert.match(html, /架空データ/);
});

test('APIエラー・入力エラー・状態表示を日本語化し、生のエラーを表示しない', async () => {
  const nodes = new Map();
  const get = (key) => {
    if (!nodes.has(key)) nodes.set(key, element());
    return nodes.get(key);
  };
  const context = vm.createContext({
    document: { querySelector: get, querySelectorAll: () => [], createElement: () => element() },
    window: { addEventListener() {} },
    fetch: async () => ({ ok: true, json: async () => [] }),
  });
  vm.runInContext(fs.readFileSync('app/static/app.js', 'utf8'), context);
  await new Promise(setImmediate);
  assert.equal(await context.responseError({ status: 403, json: async () => ({ detail: 'Document administration permission is required.' }) }), '文書管理にはADMIN権限が必要です。');
  assert.equal(await context.responseError({ status: 422, json: async () => ({ detail: [] }) }), '入力内容とユーザー設定を確認してください。');
  const safe = await context.responseError({ status: 500, json: async () => ({ detail: 'sensitive internal error' }) });
  assert.equal(safe, 'リクエストに失敗しました（HTTP 500）');
  context.renderStatuses([{ title: 'demo', document_version_id: 'V1', version_label: 'v1', status: 'active' }]);
  assert.equal(get('#document-status-list').children[0].children[2].textContent, '有効');
});
