'use strict';
const $ = (id) => document.getElementById(id);
const all = (selector) => [...document.querySelectorAll(selector)];
const titles = {
  salary: ['QUẢN LÝ ĐỘI HÌNH', 'Đội hình', 'Cân đối lương cho 11 vị trí trên sân.'],
  tax: [
    'THỊ TRƯỜNG CHUYỂN NHƯỢNG',
    'Tính thuế',
    'Biết chính xác số BP nhận được sau khi bán cầu thủ.',
  ],
  watch: [
    'THEO DÕI THỊ TRƯỜNG',
    'Canh giá',
    'Đặt ngưỡng, chọn thời điểm và theo dõi phiên giao dịch.',
  ],
};
let api,
  data,
  page = 'salary',
  busy = false,
  revision = -1,
  taxRequest = 0,
  undo = null;
let writeQueue = Promise.resolve();
let pendingWrites = 0;
function error(message) {
  $('global-error').textContent = String(message?.message || message).replace(/^Error:\s*/, '');
  $('global-error').hidden = false;
}
function saved(text, failed = false) {
  $('save-state').classList.toggle('failed', failed);
  $('save-state').lastElementChild.textContent = text;
}
function persist(method, payload) {
  const snapshot = structuredClone(payload);
  pendingWrites++;
  saved('Đang lưu…');
  writeQueue = writeQueue
    .then(() => api[method](snapshot))
    .then(() => {
      saved('Đã lưu trên máy');
    })
    .catch((e) => {
      saved('Chưa lưu được', true);
      error(e);
    })
    .finally(() => pendingWrites--);
  return writeQueue;
}
window.prepareClose = () => writeQueue.then(() => api.finish_close());
function showPage(next, save = true) {
  if (busy && next !== 'watch') return;
  page = next;
  all('.page').forEach((el) => (el.hidden = el.id !== `page-${next}`));
  all('[data-page]').forEach((el) => {
    el.classList.toggle('active', el.dataset.page === next);
    el.setAttribute('aria-current', el.dataset.page === next ? 'page' : 'false');
  });
  ['eyebrow', 'page-title', 'page-description'].forEach(
    (id, i) => ($(id).textContent = titles[next][i])
  );
  if (save) persist('save_page', next);
}
function selected(selector, attribute, value) {
  all(selector).forEach((el) => {
    const active = el.dataset[attribute] === String(value);
    el.classList.toggle('selected', active);
    el.setAttribute('aria-pressed', String(active));
  });
}
function renderPitch() {
  const formation = data.salary.formation;
  selected('[data-formation]', 'formation', formation);
  $('pitch-formation').textContent = formation.replaceAll('-', '–');
  $('players').replaceChildren();
  for (const [position, x, y] of data.formations[formation]) {
    const slot = document.createElement('div');
    slot.className = 'player-slot';
    slot.style.left = `${x * 100}%`;
    slot.style.top = `${y * 100}%`;
    const label = document.createElement('label');
    label.htmlFor = `salary-${position}`;
    label.textContent = position;
    const input = document.createElement('input');
    input.id = `salary-${position}`;
    input.className = 'player-input';
    input.inputMode = 'numeric';
    input.autocomplete = 'off';
    input.placeholder = '–';
    input.setAttribute('aria-label', `Lương ${position}`);
    input.value = data.salary.squads[formation][position];
    input.addEventListener('input', () => {
      if (!/^[0-9]*$/.test(input.value) || input.value.length > 100) {
        input.value = data.salary.squads[formation][position];
        return;
      }
      data.salary.squads[formation][position] = input.value;
      undo = null;
      $('undo-salary').hidden = true;
      renderSalary();
      persist('save_salary', data.salary);
    });
    input.addEventListener('focus', () => input.select());
    slot.append(label, input);
    $('players').append(slot);
  }
  renderSalary();
}
function group(position) {
  if (position === 'GK') return 'Thủ môn';
  if (['LB', 'LCB', 'RCB', 'RB'].includes(position)) return 'Hậu vệ';
  if (['ST', 'LW', 'RW'].includes(position)) return 'Tiền đạo';
  return 'Tiền vệ';
}
function renderSalary() {
  const squad = data.salary.squads[data.salary.formation];
  const groups = { 'Tiền đạo': 0n, 'Tiền vệ': 0n, 'Hậu vệ': 0n, 'Thủ môn': 0n };
  let total = 0n,
    count = 0;
  for (const [position, value] of Object.entries(squad)) {
    const salary = BigInt(value || '0');
    total += salary;
    groups[group(position)] += salary;
    if (value !== '') count++;
    $(`salary-${position}`)?.parentElement.classList.toggle('filled', value !== '');
  }
  $('salary-total').textContent = String(total);
  $('salary-total').style.fontSize = String(total).length > 6 ? '32px' : '';
  $('salary-count').textContent = `${count} / 11`;
  $('salary-progress').style.width = `${(count / 11) * 100}%`;
  $('salary-breakdown').replaceChildren();
  for (const [name, value] of Object.entries(groups)) {
    const row = document.createElement('div');
    row.className = 'breakdown-row';
    const label = document.createElement('span');
    label.textContent = name;
    const number = document.createElement('strong');
    number.textContent = String(value);
    const track = document.createElement('div');
    track.className = 'line-track';
    const bar = document.createElement('span');
    bar.style.width = total === 0n ? '0%' : `${Number((value * 100n) / total)}%`;
    track.append(bar);
    row.append(label, number, track);
    $('salary-breakdown').append(row);
  }
}
function taxSettings() {
  return {
    price: $('tax-price').value,
    member: data.tax.member,
    coupon: data.tax.coupon,
    pc: $('tax-pc').checked,
  };
}
async function updateTax(save = true) {
  const sequence = ++taxRequest;
  selected('[data-member]', 'member', data.tax.member);
  selected('[data-coupon]', 'coupon', data.tax.coupon);
  try {
    const settings = taxSettings();
    // Serialize writes so a slow earlier request cannot replace the last selection.
    let result;
    if (save) {
      pendingWrites++;
      writeQueue = writeQueue
        .then(async () => {
          result = await api.tax(settings, true);
        })
        .catch(() => {})
        .finally(() => pendingWrites--);
      await writeQueue;
    } else result = await api.tax(settings, false);
    if (sequence !== taxRequest) return;
    if (!result) throw new Error('Nhập số BP đầy đủ; không dùng dạng K, M, B hoặc T.');
    $('tax-price').setAttribute('aria-invalid', 'false');
    for (const [id, key] of [
      ['tax-net', 'net'],
      ['tax-fee', 'fee'],
      ['tax-saved', 'saved'],
      ['tax-gross', 'gross'],
    ])
      $(id).textContent = result[key];
    $('tax-rate').textContent = `${result.rate}%`;
    $('tax-discount').textContent = result.discount
      ? `Đã giảm ${result.discount}% tiền thuế gốc`
      : 'Chưa áp dụng giảm thuế';
    if (save) saved('Đã lưu trên máy');
  } catch (e) {
    if (sequence !== taxRequest) return;
    $('tax-price').setAttribute('aria-invalid', 'true');
    for (const id of ['tax-net', 'tax-fee', 'tax-saved', 'tax-gross']) $(id).textContent = '—';
    $('tax-rate').textContent = '';
    $('tax-discount').textContent = 'Nhập giá bán hợp lệ để tính thuế';
    saved('Kiểm tra giá bán', true);
  }
}
function watchSettings() {
  return {
    limit: $('watch-limit').value,
    dry_run: $('watch-dry').checked,
    refresh_enabled: $('watch-refresh').checked,
    reset_start: $('watch-start').value,
    reset_duration: $('watch-duration').value,
  };
}
function renderState(state) {
  if (state.revision === revision) return;
  revision = state.revision;
  busy = state.busy;
  $('watch-status').textContent = state.status;
  $('watch-dot').classList.toggle('running', busy);
  $('watch-warning').textContent = state.warning;
  $('watch-warning').hidden = !state.warning;
  $('pending-order').hidden = !state.pending;
  all('[data-page]').forEach((el) => (el.disabled = busy && el.dataset.page !== 'watch'));
  for (const id of [
    'detect',
    'diagnose',
    'watch-limit',
    'watch-start',
    'watch-duration',
    'watch-refresh',
    'watch-dry',
    'acknowledge',
  ])
    $(id).disabled = busy;
  const shot = state.snapshot;
  for (const id of ['start-watch', 'test-price', 'use-price'])
    $(id).disabled = busy || !shot || shot.quantity !== 1;
  $('stop-watch').disabled = !busy;
  $('player-empty').hidden = !!shot;
  $('player-detail').hidden = !shot;
  if (shot) {
    $('player-name').textContent = shot.name;
    $('player-boost').textContent = `+${shot.boost}`;
    $('player-quantity').textContent = `Số lượng ${shot.quantity}`;
    $('player-portrait').src = shot.portrait;
    $('player-min').textContent = shot.floor;
    $('player-max').textContent = shot.ceiling;
    $('trade-side').textContent = shot.side === 'buy' ? 'MUA · MAX' : 'BÁN · MIN';
    $('limit-label').textContent = shot.side === 'buy' ? 'Giá mua tối đa' : 'Giá bán tối thiểu';
    data.state = state;
  }
  if (state.logs.length) {
    const logs = $('logs');
    const atBottom = logs.scrollHeight - logs.scrollTop - logs.clientHeight < 30;
    logs.replaceChildren();
    for (const line of state.logs) {
      const row = document.createElement('div');
      row.className = `log-row${line.error ? ' error' : ''}`;
      const time = document.createElement('time');
      time.textContent = line.time;
      const text = document.createElement('span');
      text.textContent = line.text;
      row.append(time, text);
      logs.append(row);
    }
    if (atBottom) logs.scrollTop = logs.scrollHeight;
  }
}
async function action(name) {
  $('global-error').hidden = true;
  try {
    const state = await api.start_action(name, watchSettings());
    renderState(state);
  } catch (e) {
    error(e);
  }
}
function formatPrice(id) {
  const value = $(id).value.replace(/[.,\s]/g, '');
  if (/^[0-9]+$/.test(value))
    $(id).value = BigInt(value)
      .toString()
      .replace(/\B(?=(\d{3})+(?!\d))/g, '.');
}
async function init() {
  if (api) return;
  try {
    api = window.pywebview.api;
    data = await api.bootstrap();
    $('version').textContent = data.version;
    all('[data-page]').forEach((el) =>
      el.addEventListener('click', () => showPage(el.dataset.page))
    );
    all('[data-formation]').forEach((el) =>
      el.addEventListener('click', () => {
        data.salary.formation = el.dataset.formation;
        undo = null;
        $('undo-salary').hidden = true;
        renderPitch();
        persist('save_salary', data.salary);
      })
    );
    $('clear-salary').addEventListener('click', () => {
      undo = structuredClone(data.salary);
      Object.keys(data.salary.squads[data.salary.formation]).forEach(
        (p) => (data.salary.squads[data.salary.formation][p] = '')
      );
      renderPitch();
      persist('save_salary', data.salary);
      $('undo-salary').hidden = false;
    });
    $('undo-salary').addEventListener('click', () => {
      if (undo) {
        data.salary = undo;
        undo = null;
        renderPitch();
        persist('save_salary', data.salary);
        $('undo-salary').hidden = true;
      }
    });
    for (const value of [0, 10, 20, 30, 35, 40]) {
      const button = document.createElement('button');
      button.dataset.coupon = value;
      button.textContent = value === 0 ? 'Không' : `${value}%`;
      button.addEventListener('click', () => {
        data.tax.coupon = value;
        updateTax();
      });
      $('coupons').append(button);
    }
    all('[data-member]').forEach((el) =>
      el.addEventListener('click', () => {
        data.tax.member = el.dataset.member;
        updateTax();
      })
    );
    $('tax-price').value = data.tax.price;
    $('tax-pc').checked = data.tax.pc;
    $('tax-price').addEventListener('input', () => updateTax());
    $('tax-price').addEventListener('blur', () => formatPrice('tax-price'));
    $('tax-pc').addEventListener('change', () => updateTax());
    $('watch-limit').value = data.watch.limit;
    $('watch-dry').checked = data.watch.dry_run;
    $('watch-refresh').checked = data.watch.refresh_enabled;
    $('watch-start').value = data.watch.reset_start;
    $('watch-duration').value = data.watch.reset_duration;
    $('watch-limit').addEventListener('blur', () => formatPrice('watch-limit'));
    $('watch-dry').addEventListener('change', () => {
      $('dry-description').textContent = $('watch-dry').checked
        ? 'Làm mới bảng, không gửi lệnh'
        : 'Gửi lệnh thật khi giá đạt ngưỡng';
    });
    $('watch-dry').dispatchEvent(new Event('change'));
    for (const id of ['watch-limit', 'watch-start', 'watch-duration', 'watch-refresh', 'watch-dry'])
      $(id).addEventListener('input', () => persist('save_watch', watchSettings()));
    $('use-price').addEventListener('click', () => {
      $('watch-limit').value = data.state.snapshot.target;
      persist('save_watch', watchSettings());
    });
    $('detect').addEventListener('click', () => action('detect'));
    $('test-price').addEventListener('click', () => action('test'));
    $('start-watch').addEventListener('click', () => action('watch'));
    $('diagnose').addEventListener('click', () => action('diagnose'));
    $('stop-watch').addEventListener('click', async () => {
      try {
        renderState(await api.stop_action());
      } catch (e) {
        error(e);
      }
    });
    $('acknowledge').addEventListener('click', async () => {
      try {
        renderState(await api.acknowledge());
      } catch (e) {
        error(e);
      }
    });
    document.addEventListener('keydown', (e) => {
      if (e.key === 'F8') {
        e.preventDefault();
        api.stop_action().then(renderState).catch(error);
      }
      if (e.key === 'F9' && page === 'watch' && !busy) {
        e.preventDefault();
        action('diagnose');
      }
    });
    renderPitch();
    await updateTax(false);
    showPage(data.page, false);
    renderState(data.state);
    $('loading').hidden = true;
    document.documentElement.dataset.ready = 'true';
    const poll = async () => {
      try {
        renderState(await api.get_state());
      } catch (e) {
        saved('Mất kết nối ứng dụng', true);
      } finally {
        setTimeout(poll, 500);
      }
    };
    setTimeout(poll, 500);
  } catch (e) {
    $('loading').hidden = true;
    error(e);
  }
}
window.addEventListener('pywebviewready', init);
if (window.pywebview?.api) init();
setTimeout(() => {
  if (!api) {
    $('loading').querySelector('p').textContent =
      'Không kết nối được ứng dụng. Hãy đóng và mở lại FCO Market.';
  }
}, 12000);
