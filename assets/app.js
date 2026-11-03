(function () {
  const $ = (id) => document.getElementById(id);
  const fmt = (n) => Math.round(n).toLocaleString('vi-VN');
  const money = (n) => fmt(n) + 'đ';
  const pct = (n, d = 1) => Number(n).toLocaleString('vi-VN', { minimumFractionDigits: d, maximumFractionDigits: d }) + '%';
  const billions = (n) => (n / 1e9).toLocaleString('vi-VN', { maximumFractionDigits: 1 }) + ' tỷ';
  const dmy = (s) => s.split('-').reverse().join('/');
  const dm = (s) => s.split('-').slice(1).reverse().join('/');
  const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  const day = (s) => ['CN', 'T2', 'T3', 'T4', 'T5', 'T6', 'T7'][new Date(s + 'T00:00:00').getDay()];
  const pad = (n) => String(n).padStart(2, '0');
  const num = (n) => Number(n).toLocaleString('vi-VN');
  const balls = (main, extra = [], cls = '') => `<ul class="balls ${cls}">${main.map((n) => `<li>${pad(n)}</li>`).join('')}${extra.map((n) => `<li class="sp">${pad(n)}</li>`).join('')}</ul>`;
  const vclass = { 'Nghỉ': 'v-rest', 'Giữ vé': 'v-light', 'Chơi nhẹ': 'v-light', 'Chơi': 'v-play' };
  const names = { mega: 'Mega 6/45', power: 'Power 6/55', lotto: 'Lotto 5/35' };
  const state = { game: 'mega', shown: 5, data: null, hist: null };
  const tip = $('tip');

  const showTip = (e, html) => {
    tip.innerHTML = html;
    tip.hidden = false;
    const r = tip.getBoundingClientRect();
    tip.style.left = Math.max(8, Math.min(innerWidth - r.width - 8, e.clientX + 12)) + 'px';
    tip.style.top = Math.max(8, e.clientY - r.height - 12) + 'px';
  };
  const hideTip = () => { tip.hidden = true; };
  addEventListener('scroll', hideTip, { passive: true });

  function lastBlock(last) {
    return `<div class="picks"><h3>Kết quả kỳ trước, kỳ ${last.id}, ${day(last.date)} ${dm(last.date)}</h3>${balls(last.main, last.extra, 'sm')}
      <p class="bar-note">${last.jackpot ? `Jackpot ${billions(last.jackpot)}, ` : ''}${last.jackpot_winners ? `${last.jackpot_winners} người trúng` : 'chưa có người trúng'}</p></div>`;
  }

  function lottoCard(n, last) {
    const t = n.target;
    const note = {
      rolldown: `Kỳ này là kỳ chia giải, vé dừng bán lúc 20h30`,
      armed: `Đã vượt 12 tỷ. Kỳ chia giải dự kiến là kỳ ${t.id}, 21h ${day(t.date)} ${dm(t.date)}`,
      near: `Sắp vượt 12 tỷ, còn khoảng ${n.draws_to} kỳ nếu chưa có người trúng`,
      normal: `Còn khoảng ${n.draws_to} kỳ nữa vượt 12 tỷ nếu chưa có người trúng`,
    }[n.status];
    const title = n.tickets ? `Gợi ý ${n.tickets} vé` : 'Bộ số tham khảo';
    return `<article class="card">
      <div class="card-head"><h2>${esc(n.name)}</h2><span class="verdict ${vclass[n.verdict]}">${esc(n.verdict)}</span></div>
      <p class="meta">Kỳ ${n.id}, ${esc(n.weekday)} ${dmy(n.date)}, ${esc(n.slot)}</p>
      <div class="twin"><div><span>Độc đắc hiện tại</span><b class="prime">${billions(n.current_jackpot)}</b></div>
      <div><span>Giá trị vé 10.000đ</span><b>${money(n.ev.total)}</b></div></div>
      <div class="bar" role="img" aria-label="Độc đắc so với mốc chia giải 12 tỷ"><i style="width:${Math.min(100, n.current_jackpot / n.trigger * 100)}%"></i></div>
      <p class="bar-note">${esc(note)}</p>
      ${n.status === 'rolldown' ? '' : `<p class="bar-note">Ước tính ở kỳ chia giải: vé 10.000đ có giá trị khoảng ${money(t.ev.total)}</p>`}
      <div class="picks"><h3>${esc(title)}</h3>${n.sets.map((s) => balls(s.slice(0, 5), s.slice(5))).join('')}</div>
      ${lastBlock(last)}</article>`;
  }

  function card(n, last) {
    if (n.game === 'lotto') return lottoCard(n, last);
    const power = n.game === 'power';
    const title = n.tickets ? `Gợi ý ${n.tickets} vé` : 'Bộ số tham khảo';
    return `<article class="card">
      <div class="card-head"><h2>${esc(n.name)}</h2><span class="verdict ${vclass[n.verdict]}">${esc(n.verdict)}</span></div>
      <p class="meta">Kỳ ${n.id}, ${esc(n.weekday)} ${dmy(n.date)}</p>
      <div class="twin"><div><span>${power ? 'Jackpot 1 ước tính' : 'Jackpot ước tính'}</span><b class="prime">${billions(n.jackpot)}</b></div>
      <div><span>Giá trị vé 10.000đ</span><b>${money(n.ev.total)}</b></div></div>
      <div class="bar" role="img" aria-label="Giá trị vé bằng ${pct(n.ev.pct)} giá mua"><i style="width:${Math.min(100, n.ev.pct)}%"></i></div>
      <p class="bar-note">Bằng ${pct(n.ev.pct)} giá vé${power ? `, Jackpot 2 ước tính ${billions(n.jackpot2)}` : ''}</p>
      ${n.hold ? '<p class="bar-note">Giữ ngân sách tuần cho kỳ chia giải Lotto 5/35</p>' : ''}
      <div class="picks"><h3>${esc(title)}</h3>${n.sets.map((s) => balls(s)).join('')}</div>
      ${lastBlock(last)}</article>`;
  }

  function drawChart() {
    const lotto = state.game === 'lotto', rules = state.data.rules;
    const el = $('chart'), rows = lotto ? state.data.rolldowns.map((r) => ({ ...r, winners: 0 })) : state.data.ev_history[state.game];
    const w = el.clientWidth - 24, h = 200, m = { t: 8, r: 8, b: 24, l: 38 };
    const iw = w - m.l - m.r, ih = h - m.t - m.b;
    const top = Math.max(100, Math.ceil(Math.max(...rows.map((r) => r.pct)) / 20) * 20);
    const x = (i) => m.l + i * iw / Math.max(1, rows.length - 1);
    const y = (v) => m.t + ih - v / top * ih;
    const grid = [0, top / 2, top].map((v) => `<line x1="${m.l}" x2="${w - m.r}" y1="${y(v)}" y2="${y(v)}" stroke="var(--line)"/><text x="${m.l - 6}" y="${y(v) + 4}" text-anchor="end">${v}%</text>`).join('');
    const zone = lotto ? `<line x1="${m.l}" x2="${w - m.r}" y1="${y(100)}" y2="${y(100)}" stroke="var(--ink-2)" stroke-dasharray="4 4"/>` : `<rect x="${m.l}" width="${iw}" y="${y(rules.play_pct)}" height="${y(rules.light_pct) - y(rules.play_pct)}" fill="var(--tint)"/>`;
    const line = rows.map((r, i) => `${i ? 'L' : 'M'}${x(i).toFixed(1)} ${y(r.pct).toFixed(1)}`).join(' ');
    const dots = rows.map((r, i) => `<circle cx="${x(i)}" cy="${y(r.pct)}" r="${r.winners ? 5 : 3}" fill="${r.winners ? 'var(--gold)' : 'var(--red)'}" stroke="var(--red)" stroke-width="1.5"/>`).join('');
    const hits = rows.map((r, i) => `<rect data-i="${i}" x="${x(i) - iw / rows.length / 2}" y="${m.t}" width="${iw / rows.length}" height="${ih}" fill="transparent"/>`).join('');
    const ticks = [0, rows.length - 1].map((i) => `<text x="${x(i)}" y="${h - 6}" text-anchor="${i ? 'end' : 'start'}">Kỳ ${rows[i].id}</text>`).join('');
    el.innerHTML = `<svg viewBox="0 0 ${w} ${h}" height="${h}" role="img" aria-label="Giá trị vé so với giá mua theo từng kỳ">${grid}${zone}<path d="${line}" fill="none" stroke="var(--red)" stroke-width="2"/>${dots}${ticks}${hits}</svg><p class="bar-note">${lotto ? 'Đường nét đứt là mức hòa vốn 100%.' : 'Vùng hồng là mức chơi nhẹ, chấm vàng là kỳ có người trúng jackpot.'}</p>`;
    el.querySelectorAll('rect[data-i]').forEach((node) => {
      const r = rows[+node.dataset.i];
      const on = (e) => showTip(e, `Kỳ ${r.id}, ${dmy(r.date)}<br>Jackpot ${billions(r.jackpot)}${r.tickets ? `<br>Vé bán khoảng ${(r.tickets / 1e6).toLocaleString('vi-VN', { maximumFractionDigits: 2 })} triệu` : ''}<br>Giá trị vé ${pct(r.pct)}`);
      node.addEventListener('pointermove', on);
      node.addEventListener('pointerdown', on);
      node.addEventListener('pointerleave', hideTip);
    });
  }

  function drawGame() {
    const d = state.data, rows = state.hist[state.game], power = state.game === 'power';
    $('draws').innerHTML = rows.slice(0, state.shown).map((r) => {
      const won = [];
      if (r.winners) won.push(`${power ? 'JP1 ' : ''}${r.winners} người trúng`);
      if (r.winners2) won.push(`JP2 ${r.winners2} người trúng`);
      const value = !r.jackpot ? '' : state.game === 'lotto' ? `Độc đắc ${billions(r.jackpot)}` : power ? `JP1 ${billions(r.jackpot)}${r.jackpot2 ? `, JP2 ${billions(r.jackpot2)}` : ''}` : `Jackpot ${billions(r.jackpot)}`;
      if (r.rolldown) won.push('Kỳ chia giải');
      return `<li class="row"><div class="when"><b>Kỳ ${r.id}</b> <span>${day(r.date)} ${dmy(r.date)}</span></div>${balls(r.main, r.extra, 'sm')}<div class="prize">${value}${won.length ? `<span class="won">${won.join(', ')}</span>` : ''}</div></li>`;
    }).join('');
    $('more').hidden = state.shown >= rows.length;
    const lotto = state.game === 'lotto';
    const b = d.breakeven[state.game] || {}, lb = d.lotto_breakeven;
    const million = (n) => (n / 1e6).toLocaleString('vi-VN', { maximumFractionDigits: 2 }) + ' triệu vé';
    $('value-title').textContent = lotto ? 'Các kỳ chia giải đã ghi nhận' : 'Giá trị vé theo kỳ';
    $('value-note').textContent = lotto
      ? 'Ở kỳ chia giải, Độc đắc được trả hết cho các vé trúng, nên giá trị vé phụ thuộc vào số vé bán. Vé bán ngày càng nhiều nên lợi thế đang giảm dần.'
      : '';
    $('marks').innerHTML = lotto
      ? `<div><dt>Hòa vốn, Độc đắc 13 tỷ</dt><dd>${million(lb['13'])}</dd></div><div><dt>Hòa vốn, Độc đắc 20 tỷ</dt><dd>${million(lb['20'])}</dd></div><div><dt>Hòa vốn, Độc đắc 30 tỷ</dt><dd>${million(lb['30'])}</dd></div>`
      : `<div><dt>Chơi nhẹ từ</dt><dd>${billions(b['45'])}</dd></div><div><dt>Chơi từ</dt><dd>${billions(b['55'])}</dd></div><div><dt>Hòa vốn từ</dt><dd>${billions(b['100'])}</dd></div>`;
    drawChart();
  }

  function render(d) {
    state.data = d;
    const stale = (Date.now() - new Date(d.generated_at).getTime()) / 36e5 > 36;
    $('stamp').textContent = `Cập nhật ${d.generated_at.slice(11, 16)} ${dm(d.today)}`;
    $('headline').textContent = d.commentary.headline;
    $('commentary').innerHTML = d.commentary.paragraphs.map((p) => `<p>${esc(p)}</p>`).join('');
    const warn = [...d.warnings];
    if (stale) warn.unshift(`Trang chưa được cập nhật từ ${dmy(d.today)}, số liệu có thể đã cũ.`);
    const lotto = d.next.find((n) => n.game === 'lotto');
    if (lotto.status === 'rolldown') warn.unshift(`Hôm nay có kỳ chia giải Lotto 5/35, kỳ ${lotto.id} lúc 21h. Vé dừng bán lúc 20h30.`);
    if (lotto.status === 'armed') warn.unshift(`Lotto 5/35 đã vượt 12 tỷ. Kỳ chia giải dự kiến là kỳ ${lotto.target.id}, 21h ${dmy(lotto.target.date)}, vé dừng bán lúc 20h30.`);
    if (lotto.status === 'near') warn.unshift(`Lotto 5/35 sắp vượt 12 tỷ, tạm giữ ngân sách tuần cho kỳ chia giải.`);
    $('alerts').innerHTML = warn.map((w) => `<p>${esc(w)}</p>`).join('');
    $('cards').innerHTML = d.next.map((n) => card(n, d.latest[n.game])).join('');

    const p = d.portfolio;
    $('book-note').textContent = p.spent || p.week_used
      ? `Theo dõi từ ${dmy(p.start)}, không phải tiền thật. Trần ${p.week_cap} vé mỗi tuần, ưu tiên kỳ chia giải Lotto 5/35.`
      : `Theo dõi từ ${dmy(p.start)}, không phải tiền thật. Số liệu đang bằng 0 vì các kỳ tới đều chấm Nghỉ. Trần ${p.week_cap} vé mỗi tuần, ưu tiên kỳ chia giải Lotto 5/35.`;
    $('book-facts').innerHTML = `<div><dt>Đã dùng tuần này</dt><dd>${p.week_used}/${p.week_cap} vé</dd></div>
      <div><dt>Đã chi</dt><dd>${money(p.spent)}</dd></div>
      <div><dt>Thu về, bộ số gợi ý</dt><dd>${money(p.returned)}</dd></div>
      <div><dt>Thu về, ngẫu nhiên</dt><dd>${money(p.returned_baseline)}</dd></div>`;
    $('log').innerHTML = p.log.slice(0, 8).map((e) => `<li class="row"><div class="when"><b>${names[e.game]}, kỳ ${e.id}</b><span>${day(e.date)} ${dmy(e.date)}, giá trị vé ${pct(e.ev_pct)}</span></div>
      <span class="verdict ${vclass[e.verdict]}">${esc(e.verdict)}</span>
      ${e.numbers ? balls(e.numbers.slice(0, e.game === 'lotto' ? 5 : 6), e.numbers.slice(e.game === 'lotto' ? 5 : 6), 'sm') : '<p class="wait">Chờ kết quả</p>'}</li>`).join('');

    const ac = d.accuracy, cols = ['mega', 'power', 'lotto'];
    const acRow = (label, get) => `<div><span>${label}</span>${cols.map((g) => `<span>${get(ac.games[g])}</span>`).join('')}</div>`;
    const off = (v) => (v === null ? 'Chưa có' : pct(v));
    const scored = cols.reduce((n, g) => n + ac.games[g].scored, 0);
    $('acc-note').textContent = scored
      ? `Sổ dự báo bắt đầu từ ${dmy(ac.start)}. Mỗi kỳ lấy dự báo gần giờ quay nhất so với kết quả thật.`
      : `Sổ dự báo bắt đầu từ ${dmy(ac.start)}. Chưa có kỳ nào đủ kết quả để chấm.`;
    $('acc').innerHTML = `<div><span></span><b>Mega</b><b>Power</b><b>Lotto</b></div>
      ${acRow('Số kỳ đã chấm', (x) => x.scored)}
      ${acRow('Sai số jackpot', (x) => off(x.jackpot_error))}
      ${acRow('Sai số vé bán', (x) => off(x.tickets_error))}
      ${acRow('Số trùng bộ số, thực tế', (x) => (x.set_hits === null ? 'Chưa có' : num(x.set_hits)))}
      ${acRow('Số trùng kỳ vọng', (x) => num(x.set_hits_expected))}`;
    const t = d.tests, f = d.filter_check;
    const row = (label, get) => `<div><span>${label}</span>${['mega', 'power', 'lotto'].map((g) => `<span>${num(get(t[g]))}</span>`).join('')}</div>`;
    $('tests').innerHTML = `<p><b>Chưa thấy dấu hiệu đoán được.</b> Số liệu dưới đây dựa trên ${fmt(t.mega.draws)} kỳ Mega, ${fmt(t.power.draws)} kỳ Power và ${fmt(t.lotto.draws)} kỳ Lotto.</p>
      <div class="facts"><div><span></span><b>Mega</b><b>Power</b><b>Lotto</b></div>
      ${row('Độ đều của các số (p, trên 0,05 là bình thường)', (x) => x.p)}
      ${row('Số trùng mỗi kỳ nếu chọn số nóng', (x) => x.hot.mean)}
      ${row('Số trùng mỗi kỳ nếu chọn số lạnh', (x) => x.cold.mean)}
      ${row('Số trùng kỳ vọng khi chọn ngẫu nhiên', (x) => x.hot.expected)}</div>
      ${t.lotto.p < 0.05 ? '<p>Lotto có p thấp hơn mức thường, nhưng khi chạy nhiều phép thử thì điều này có thể do ngẫu nhiên. Trang tiếp tục theo dõi và không dùng để chọn số.</p>' : ''}
      <p>Bộ số gợi ý không làm tăng khả năng trúng: tỷ lệ vé trúng từ giải ba trở lên là ${pct(f.filter_win_pct, 2)}, so với ${pct(f.random_win_pct, 2)} khi chọn ngẫu nhiên. Việc tránh số đông người chọn mới là giả thuyết, dữ liệu hiện chưa đủ chứng minh.</p>`;
    $('method').innerHTML = `<p><b>Giá trị vé</b> là số tiền bình quân một vé thu về: xác suất từng giải nhân tiền thực nhận, đã trừ thuế 10% phần giải vượt 20 triệu và rủi ro chia giải.</p>
      <p><b>Nhận định:</b> dưới ${d.rules.light_pct}% nghỉ, từ ${d.rules.light_pct}% chơi nhẹ ${d.rules.light_tickets} vé, từ ${d.rules.play_pct}% chơi ${d.rules.play_tickets} vé, tối đa ${d.rules.week_tickets} vé mỗi tuần. Đây là ngưỡng do trang đặt ra. Mốc hòa vốn là gần đúng vì vé bán thường tăng khi jackpot cao.</p>
      <p><b>Lotto 5/35:</b> khi Độc đắc vượt 12 tỷ mà chưa có người trúng, kỳ 21h ngày hôm sau là kỳ chia giải. Giải Nhất nhận 1/3, các giải Nhì đến Năm mỗi giải nhận 1/6 giá trị Độc đắc. Giá trị vé ở kỳ này bằng phần chia sau thuế trên mỗi vé cộng ${money(d.lotto_fixed)} giải cố định, số vé bán lấy theo tỷ lệ của kỳ chia giải gần nhất. Kỳ thường luôn chấm Nghỉ.</p>
      <p><b>Sổ dự báo:</b> mỗi lượt chạy lưu lại số ước tính, nhận định và bộ số của các kỳ tới, rồi tự chấm khi có kết quả. Sổ này dùng để căn chỉnh công thức ước tính, không giúp dự đoán số trúng.</p>
      <p><b>Ước tính:</b> số vé bán suy từ số người trúng giải ba các kỳ gần đây, jackpot kỳ tới bằng mức hiện tại cộng bình quân 2 bước tăng gần nhất của chu kỳ đang chạy.</p>
      <p><b>Nguồn:</b> dãy số từ <a href="https://github.com/vietvudanh/vietlott-data">vietlott-data</a>, jackpot và số người trúng từ <a href="https://xosodaiphat.com/xs-mega-xo-so-mega-645.html">Xổ số Đại Phát</a>. Dữ liệu Lotto từ <a href="https://www.minhchinh.com/xo-so-dien-toan-lotto-535.html">Minh Chính</a>. Các nguồn được đối chiếu dãy số mỗi lần cập nhật. Danh sách kỳ chia giải cũ lấy từ báo chí nên có thể chưa đủ. Mega có dữ liệu từ kỳ ${t.mega.first_id}, jackpot lưu từ tháng 3/2026, Mega trước tháng 10/2026 làm tròn đến nghìn đồng.</p>`;
  }

  document.querySelectorAll('.switch button').forEach((btn) => btn.addEventListener('click', () => {
    state.game = btn.dataset.game;
    state.shown = 5;
    document.querySelectorAll('.switch button').forEach((b) => b.setAttribute('aria-pressed', String(b === btn)));
    drawGame();
  }));
  $('more').addEventListener('click', () => { state.shown += 20; drawGame(); });
  addEventListener('resize', () => { if (state.hist) drawChart(); });

  const load = (path) => fetch(`data/${path}?v=${Date.now()}`).then((r) => { if (!r.ok) throw new Error(r.status); return r.json(); });
  Promise.all([load('dashboard.json'), load('history.json')])
    .then(([d, h]) => { render(d); state.hist = h; drawGame(); })
    .catch(() => {
      $('headline').textContent = 'Chưa tải được số liệu';
      $('commentary').innerHTML = '<p>Tải lại trang sau ít phút.</p>';
    });
})();
