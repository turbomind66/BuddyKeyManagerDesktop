const state = { sessions: [], credentials: [], currentSms: null };

const $ = (selector) => document.querySelector(selector);
const escapeHtml = (value) => String(value ?? '').replace(/[&<>\"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;',"'":'&#39;'}[c]));
const jsString = (value) => JSON.stringify(String(value ?? '')).replace(/</g, '\\u003c').replace(/>/g, '\\u003e').replace(/&/g, '\\u0026');
const fmtTime = (ts) => ts ? new Date(ts * 1000).toLocaleString() : '-';

async function api(url, options = {}) {
  const response = await fetch(url, { headers: {'Content-Type': 'application/json', ...(options.headers || {})}, ...options });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.detail || data.message || `HTTP ${response.status}`);
  return data;
}

function showMessage(message, error = false) {
  const box = $('#message');
  box.textContent = message;
  box.className = error ? 'message error' : 'message success';
  setTimeout(() => { box.textContent = ''; box.className = 'message'; }, 5000);
}

function renderSessions() {
  const el = $('#sessions');
  if (!state.sessions.length) { el.innerHTML = '<div class="empty">暂无授权会话</div>'; return; }
  el.innerHTML = state.sessions.map(s => `
    <div class="session-item">
      <div><strong>${escapeHtml(s.region_name)} · ${escapeHtml(s.platform)}</strong><small>${fmtTime(s.created_at)}</small></div>
      <span class="badge ${s.status}">${escapeHtml(s.status_name)}${s.last_error ? `：${escapeHtml(s.last_error)}` : ''}</span>
      <button class="text-btn" onclick="deleteSession('${s.id}')">删除</button>
    </div>`).join('');
}

function healthBadge(c) {
  if (c.risk_controlled) return '<span class="badge risk">风控</span>';
  if (c.alive === true) return '<span class="badge healthy">有效</span>';
  if (c.alive === false) return '<span class="badge dead">失效/异常</span>';
  return '<span class="badge unknown">未测</span>';
}

function renderCredentials() {
  const filter = $('#health-filter').value;
  const rows = state.credentials.filter(c => filter === 'all' || (filter === 'healthy' && c.alive === true && !c.risk_controlled) || (filter === 'risk' && c.risk_controlled) || (filter === 'dead' && c.alive === false && !c.risk_controlled) || (filter === 'unknown' && c.alive === null));
  const el = $('#credentials');
  if (!rows.length) { el.innerHTML = '<div class="empty">暂无凭证</div>'; return; }
  el.innerHTML = rows.map(c => `
    <div class="credential-item">
      <div class="credential-main"><strong>${escapeHtml(c.note || c.nickname || c.uid)}</strong><small>${c.note ? escapeHtml(c.nickname) + ' · ' : ''}${escapeHtml(c.uid)} · ${escapeHtml(c.region_name)}</small></div>
      <div class="credential-meta">${healthBadge(c)}<span>余额：${c.balance < 0 ? '-' : c.balance}</span><span>到期：${fmtTime(c.expires_at)}</span></div>
      <div class="credential-actions">
        <button onclick="pingOne(${jsString(encodeURIComponent(c.key || c.uid))})">测活</button>
        <button onclick="balanceOne(${jsString(encodeURIComponent(c.key || c.uid))})">余额</button>
        <button onclick="pushOne(${jsString(encodeURIComponent(c.key || c.uid))})">推送</button>
        <button onclick="editNote(${jsString(encodeURIComponent(c.key || c.uid))}, ${jsString(c.note || '')})">备注</button>
        <button class="danger" onclick="deleteCredential(${jsString(encodeURIComponent(c.key || c.uid))})">删除</button>
      </div>
    </div>`).join('');
}

async function refreshAll() {
  try {
    const [sessions, credentials, settings] = await Promise.all([api('/api/auth/sessions'), api('/api/credentials'), api('/api/settings')]);
    state.sessions = sessions; state.credentials = credentials;
    $('#sms-provider').value = settings.sms_provider || 'ejiema';
    $('#sms-token').value = '';
    $('#sms-configured').textContent = settings.sms_configured ? '已配置' : '未配置';
    $('#push-url').value = settings.push_base_url || '';
    $('#push-password').value = '';
    $('#push-configured').textContent = settings.push_configured ? '已配置' : '未配置';
    renderSessions(); renderCredentials();
  } catch (e) { showMessage(e.message, true); }
}

async function createSession() {
  const button = $('#create-session'); button.disabled = true;
  try {
    const data = await api('/api/auth/sessions', {method: 'POST', body: JSON.stringify({region: $('#region').value, platform: 'CLI'})});
    showMessage('授权链接已创建，已在默认浏览器打开。请在浏览器中完成登录。');
    await refreshAll();
  } catch (e) { showMessage(e.message, true); }
  finally { button.disabled = false; }
}

async function deleteSession(id) { try { await api(`/api/auth/sessions/${id}`, {method: 'DELETE'}); await refreshAll(); } catch (e) { showMessage(e.message, true); } }
async function pingOne(uid) { try { showMessage('正在测活…'); await api(`/api/credentials/${uid}/ping`, {method: 'POST'}); await refreshAll(); showMessage('测活完成'); } catch (e) { showMessage(e.message, true); } }
async function balanceOne(uid) { try { showMessage('正在查询余额…'); const r = await api(`/api/credentials/${uid}/balance`, {method: 'POST'}); await refreshAll(); showMessage(`余额查询完成：${r.total}`); } catch (e) { showMessage(e.message, true); } }
async function pushOne(uid) { try { showMessage('正在推送凭证…'); await api(`/api/credentials/${uid}/push`, {method: 'POST'}); showMessage('推送成功'); } catch (e) { showMessage(e.message, true); } }
async function deleteCredential(uid) { if (!confirm('确定删除该凭证？此操作不可撤销。')) return; try { await api(`/api/credentials/${uid}`, {method: 'DELETE'}); await refreshAll(); } catch (e) { showMessage(e.message, true); } }
async function editNote(uid, oldNote) { const note = prompt('输入备注（留空则清除）：', oldNote); if (note === null) return; try { await api(`/api/credentials/${uid}`, {method: 'PATCH', body: JSON.stringify({note})}); await refreshAll(); } catch (e) { showMessage(e.message, true); } }

async function saveSmsSettings() {
  const token = $('#sms-token').value.trim();
  try { await api('/api/settings/sms', {method: 'PUT', body: JSON.stringify({provider: $('#sms-provider').value, token})}); $('#sms-token').value = ''; await refreshAll(); showMessage('接码平台设置已保存'); } catch (e) { showMessage(e.message, true); }
}

async function smsAction(action) {
  try {
    const payload = {keyword: $('#sms-keyword').value.trim(), phone: $('#sms-phone').value.trim()};
    const r = await api(`/api/sms/${action}`, {method: 'POST', body: JSON.stringify(payload)});
    if (action === 'get_phone') $('#sms-phone').value = r.phone || '';
    if (action === 'get_message') { $('#sms-message').value = r.message || ''; $('#sms-code').value = r.code || ''; }
    showMessage(r.message || r.phone || '操作完成');
  } catch (e) { showMessage(e.message, true); }
}

$('#create-session').onclick = createSession;
$('#refresh').onclick = refreshAll;
$('#health-filter').onchange = renderCredentials;
$('#save-sms').onclick = saveSmsSettings;
$('#save-push').onclick = async () => { try { await api('/api/settings/push', {method: 'PUT', body: JSON.stringify({base_url: $('#push-url').value.trim(), password: $('#push-password').value})}); $('#push-password').value = ''; await refreshAll(); showMessage('Buddy2API 设置已保存'); } catch(e) { showMessage(e.message, true); } };
$('#push-all').onclick = async () => { try { showMessage('正在批量推送…'); const result = await api('/api/credentials/push-all', {method: 'POST'}); const ok = result.filter(x => x.ok).length; showMessage(`批量推送完成：成功 ${ok}，失败 ${result.length - ok}`); } catch(e) { showMessage(e.message, true); } };
$('#sms-phone-btn').onclick = () => smsAction('get_phone');
$('#sms-message-btn').onclick = () => smsAction('get_message');
$('#sms-release').onclick = () => smsAction('release');
$('#sms-block').onclick = () => smsAction('block');
$('#ping-all').onclick = async () => { try { showMessage('开始批量测活，请耐心等待…'); await api('/api/credentials/ping-all', {method: 'POST'}); await refreshAll(); showMessage('批量测活完成'); } catch(e) { showMessage(e.message, true); } };
$('#export').onclick = () => { if (confirm('导出文件包含敏感 Token，请确认仅保存到安全位置。')) window.location.href = '/api/credentials/export'; };

refreshAll();
setInterval(refreshAll, 5000);
