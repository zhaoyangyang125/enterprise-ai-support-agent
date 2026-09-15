// Node内置测试：使用假的DOM和网络，不发送真实资料。
const { test } = require('node:test');
const assert = require('node:assert/strict');
require('../app/static/image-evidence.js');

function element() {
  return { children: [], events: {}, hidden: false,
    append(...items) { this.children.push(...items); },
    setAttribute() {}, removeAttribute(name) { delete this[name]; },
    addEventListener(name, callback) { this.events[name] = callback; } };
}
const source = { image_url: '/api/documents/D/versions/V/assets/img_' + 'a'.repeat(64) };

test('图片成功加载携带身份，重新加载与销毁释放资源', async () => {
  global.document = { createElement: element };
  const revoked = [];
  URL.createObjectURL = () => 'blob:test';
  URL.revokeObjectURL = (url) => revoked.push(url);
  global.fetch = async (url, options) => {
    assert.equal(url, source.image_url);
    assert.equal(options.headers['X-User-Id'], 'U001');
    assert.equal(options.redirect, 'error');
    return { ok: true, status: 200, blob: async () => ({ type: 'image/png' }) };
  };
  const card = element();
  const dispose = attachImageEvidence(card, source, () => ({ 'X-User-Id': 'U001' }));
  await card.children[0].events.click();
  assert.equal(card.children[2].src, 'blob:test');
  await card.children[0].events.click();
  dispose();
  assert.equal(revoked.length, 2);
  assert.equal(card.children[2].hidden, true);
});

test('拒绝外部URL，纯文字引用不添加图片控件', () => {
  for (const item of [{}, { image_url: 'https://evil.test/image' }]) {
    const card = element();
    assert.equal(attachImageEvidence(card, item, () => ({})), undefined);
    assert.equal(card.children.length, 0);
  }
});

test('权限、缺图、网络和非图片响应安全降级', async () => {
  global.document = { createElement: element };
  for (const code of [403, 404, 500, 'network', 'mime']) {
    global.fetch = async () => {
      if (code === 'network') throw new Error('offline');
      return { status: code, ok: code === 'mime', blob: async () => ({ type: 'text/html' }) };
    };
    const card = element();
    attachImageEvidence(card, source, () => ({}));
    await card.children[0].events.click();
    assert.equal(card.children[2].hidden, true);
    assert.equal(card.children[0].disabled, false);
    assert.ok(card.children[1].textContent);
  }
});

test('身份切换销毁后，迟到的响应不能显示', async () => {
  global.document = { createElement: element };
  let resolve;
  global.fetch = () => new Promise((done) => { resolve = done; });
  const card = element();
  const dispose = attachImageEvidence(card, source, () => ({}));
  const pending = card.children[0].events.click();
  dispose();
  resolve({ ok: true, status: 200, blob: async () => ({ type: 'image/png' }) });
  await pending;
  assert.equal(card.children[2].hidden, true);
  assert.equal(card.children[2].src, undefined);
});
