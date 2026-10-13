const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const html = fs.readFileSync('app/public_static/index.html', 'utf8');
const script = fs.readFileSync('app/public_static/public.js', 'utf8');

function node() {
  return { value: '', dataset: {}, events: {}, children: [], disabled: false,
    addEventListener(name, callback) { this.events[name] = callback; },
    append(child) { this.children.push(child); }, focus() {}, remove() { this.removed = true; },
  };
}

function setup(response) {
  const nodes = new Map();
  const get = selector => {
    if (!nodes.has(selector)) nodes.set(selector, node());
    return nodes.get(selector);
  };
  const buttons = [...html.matchAll(/data-prompt="([^"]+)"/g)].map(match => {
    const button = node(); button.dataset.prompt = match[1]; return button;
  });
  const requests = [];
  vm.runInNewContext(script, {
    document: { querySelector: get, querySelectorAll: () => buttons, createElement: node },
    AbortController, setTimeout, clearTimeout,
    fetch: async (url, options) => { requests.push({ url, options }); return response; },
  });
  return { get, buttons, requests };
}

test('公開質問例は入力のみで通信せず、管理用UIがない', () => {
  const ui = setup({});
  assert.equal(ui.buttons.length, 3);
  for (const button of ui.buttons) {
    button.events.click();
    assert.equal(ui.get('#message').value, button.dataset.prompt);
  }
  assert.equal(ui.requests.length, 0);
  assert.match(html, /架空データを使用した公開デモです/);
  assert.doesNotMatch(html, /upload-form|role-ids|user-id|ADMIN|leave-requests/);
});

test('公開チャットは身份Headerを送らず、回答とCitationをtextContentで表示', async () => {
  const payload = '<img src=x onerror=alert(1)>';
  const ui = setup({ ok: true, json: async () => ({ answer: payload,
    sources: [{ location: 'TravelPolicy_v1.pdf / Page 3', section: '2.1 国内出張' }] }) });
  ui.get('#message').value = '国内出張の宿泊費上限はいくらですか？';
  await ui.get('#chat-form').events.submit({ preventDefault() {} });
  assert.equal(ui.requests.length, 1);
  assert.equal(ui.requests[0].url, '/api/chat');
  assert.deepEqual(Object.keys(ui.requests[0].options.headers), ['Content-Type']);
  const messages = ui.get('#chat-feed').children;
  const answer = messages[messages.length - 1];
  assert.equal(answer.children[1].textContent, payload);
  assert.equal(answer.children[3].children[0].children[0].textContent, 'TravelPolicy_v1.pdf / Page 3');
  assert.doesNotMatch(script, /innerHTML/);
  assert.equal(ui.get('#send-button').disabled, false);
});

test('公開429は日本語で表示し送信ボタンを復旧', async () => {
  const ui = setup({ ok: false, status: 429 });
  ui.get('#message').value = '有給残日数';
  await ui.get('#chat-form').events.submit({ preventDefault() {} });
  const messages = ui.get('#chat-feed').children;
  assert.match(messages[messages.length - 1].children[1].textContent, /利用上限/);
  assert.equal(ui.get('#send-button').disabled, false);
});
