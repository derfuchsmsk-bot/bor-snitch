// Run with: node tests/check_debts_ui.cjs
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const { randomUUID } = require('node:crypto');

const source = fs.readFileSync('src/admin/ui.py', 'utf8');
const start = source.indexOf('    // --- TAB: DEBTS & BALANCES ---');
const end = source.indexOf('    // --- TAB: LORE & FACTS ---', start);
const elements = {
  'modal-debt-edit': { dataset: { chatId: '1' } },
  'modal-debt-debtor': { value: 'alice' },
  'modal-debt-creditor': { value: 'bob' },
  'modal-debt-amount': { value: '500' },
  'modal-debt-is-delta': { checked: true },
};
const calls = [];
const actions = [];
const buttons = ['settle', 'edit', 'delete'].map(action => ({
  dataset: { debtAction: action, debtIndex: '0' },
  addEventListener(event, callback) { this.click = callback; },
}));
elements['debts-table-body'] = { innerHTML: '', querySelectorAll: () => buttons };
let finish;
const context = vm.createContext({
  state: { currentChatId: 1 },
  document: { getElementById: id => elements[id] },
  crypto: { randomUUID },
  apiRequest: (path, options) => new Promise((resolve, reject) => {
    calls.push({ path, payload: JSON.parse(options.body) });
    finish = { resolve, reject };
  }),
  showToast() {}, closeModal() {},
  capture: (...args) => actions.push(args),
});
vm.runInContext(source.slice(start, end), context);
const escapeStart = source.indexOf('    function escapeHtml(str)');
vm.runInContext(source.slice(escapeStart, source.indexOf('    // --- Helpers: Toast', escapeStart)), context);
vm.runInContext('loadDebts = () => {}', context);

(async () => {
  const first = vm.runInContext('submitSaveDebt()', context);
  await vm.runInContext('submitSaveDebt()', context);
  assert.equal(calls.length, 1, 'double click must not send another mutation');
  finish.reject(new Error('response lost'));
  await first;
  const retry = vm.runInContext('submitSaveDebt()', context);
  assert.equal(calls[1].payload.request_id, calls[0].payload.request_id, 'retry must reuse idempotency key');
  finish.resolve({});
  await retry;
  const next = vm.runInContext('submitSaveDebt()', context);
  assert.notEqual(calls[2].payload.request_id, calls[1].payload.request_id, 'new action must get a new key');
  finish.resolve({});
  await next;
  elements['modal-debt-amount'].value = '500.5';
  await vm.runInContext('submitSaveDebt()', context);
  assert.equal(calls.length, 3, 'fractional amount must be rejected without rounding');
  elements['modal-debt-amount'].value = '500';
  context.state.currentChatId = 2;
  await vm.runInContext('submitSaveDebt()', context);
  assert.equal(calls.length, 3, 'old modal must not write to a newly selected chat');
  const debtor = "O'Neil <img src=x onerror=alert(1)>";
  vm.runInContext(`
    openSettleDebtModal = (...args) => capture('settle', ...args);
    openEditDebtModal = (...args) => capture('edit', ...args);
    deleteDebtPair = (...args) => capture('delete', ...args);
    renderDebtsTable(${JSON.stringify([{ debtor, creditor: 'bob', amount: 500 }])});
  `, context);
  assert.ok(!elements['debts-table-body'].innerHTML.includes('onclick='));
  assert.ok(!elements['debts-table-body'].innerHTML.includes('<img'));
  buttons.forEach(button => button.click());
  assert.equal(actions.length, 3);
  actions.forEach(action => assert.equal(action[1], debtor, 'button must preserve the original name'));
  console.log('Debt UI: double click, retry, new operation, fractional input, chat switch and escaped names passed.');
})().catch(error => { console.error(error); process.exitCode = 1; });
