// モック API ハンドラ。src/api/index.js から呼ばれ、Flask API と同じ形のデータを返す。
import * as db from './db';
import { runAgent } from './agent';

const delay = (ms = 250) => new Promise((r) => setTimeout(r, ms));
const clone = (v) => structuredClone(v);
let seq = 1000;
const genId = (prefix) => `${prefix}${++seq}`;
const now = () => new Date().toISOString();

class MockError extends Error {
  constructor(status, message) {
    super(message);
    this.status = status;
  }
}

// ---------- セッション（Flask の Cookie セッションの代わり） ----------
const SESSION_KEY = 'mock_session_user_id';
function currentUser() {
  const id = sessionStorage.getItem(SESSION_KEY);
  const user = db.users.find((u) => u.id === id);
  if (!user) throw new MockError(401, 'ログインが必要です');
  return user;
}
function requireRole(...roles) {
  const user = currentUser();
  if (!roles.includes(user.role)) throw new MockError(403, '権限がありません');
  return user;
}

export async function login(email, password) {
  await delay(400);
  const user = db.users.find((u) => u.email === email.trim());
  if (!user || !password) throw new MockError(401, 'メールアドレスまたはパスワードが正しくありません');
  if (user.status === 'suspended') throw new MockError(403, 'このアカウントは利用停止中です');
  user.lastLoginAt = now();
  sessionStorage.setItem(SESSION_KEY, user.id);
  return clone(user);
}
export async function logout() {
  sessionStorage.removeItem(SESSION_KEY);
  return null;
}
export async function me() {
  await delay(50);
  return clone(currentUser());
}

// ---------- マスタ ----------
export async function getDepartments() {
  return clone(db.departments);
}
export async function getCategories() {
  return clone(db.categories);
}

// ---------- 初期データ（会話履歴・利用ログ） ----------
function seed() {
  const u1 = db.users.find((u) => u.id === 'u1');
  const conv = (id, question, at, extra = {}) => {
    const { message } = runAgent(question, u1);
    Object.assign(message, { createdAt: at }, extra);
    db.conversations.push({
      id,
      userId: 'u1',
      title: question.replace(/[？?]$/, '').slice(0, 24),
      createdAt: at,
      updatedAt: at,
      messages: [{ id: genId('m'), role: 'user', content: question, createdAt: at }, message],
    });
  };
  conv('c1', '引越しをしたら何を申請すればいい？', '2026-10-01T12:10:00', { feedback: 'good' });
  conv('c2', '社用スマホの画面が割れた。どうすればいい？', '2026-09-26T10:05:00', { inquiryId: 'q3' });
  conv('c3', 'パスワードを忘れてログインできない', '2026-09-24T09:30:00');
  conv('c4', '経費精算の締め日はいつ？', '2026-09-10T17:20:00', { feedback: 'good' });

  // 利用ログ（擬似乱数で生成）
  let r = 7;
  const rand = () => ((r = (r * 9301 + 49297) % 233280) / 233280);
  const questions = [
    '結婚したんだけど会社で必要な手続きってある？', '引越しをしたら何を申請すればいい？', 'パスワードを忘れてログインできない',
    '経費精算の締め日はいつ？', '育休はいつまでに申請すればいい？', '副業ってしてもいいの？', '出産祝金はもらえる？',
    '住所変更の届出期限は？', 'VPNにつながらない', '領収書をなくした場合はどうする？', '会議室を土日に使いたい', '海外出張の日当はいくら？',
  ];
  const actors = db.users.filter((u) => u.status === 'active');
  for (let i = 0; i < 48; i++) {
    const user = actors[Math.floor(rand() * actors.length)];
    const question = questions[Math.floor(rand() * questions.length)];
    const { message, scenarioId } = runAgent(question, user);
    const at = new Date(Date.parse('2026-10-02T09:00:00') - Math.floor(rand() * 30 * 24 * 60) * 60000).toISOString();
    const result = message.inquirySuggestion ? (rand() > 0.4 ? 'inquiry' : 'no_answer') : 'resolved';
    const fb = rand();
    db.logs.push({
      id: genId('l'), at, userId: user.id, userName: user.name, department: user.department, question, scenarioId,
      searchCount: message.agent.searchCount, sourceCount: message.sources.length,
      result, feedback: fb > 0.55 ? 'good' : fb > 0.45 ? 'bad' : null,
      durationMs: message.agent.durationMs + Math.floor(rand() * 1500),
      steps: message.agent.steps, sources: message.sources.map((s) => `${s.title} ${s.section}`),
    });
  }
  db.logs.sort((a, b) => Date.parse(b.at) - Date.parse(a.at));
}
seed();

// ---------- チャット ----------
export async function listConversations() {
  await delay(100);
  const user = currentUser();
  return db.conversations
    .filter((c) => c.userId === user.id)
    .sort((a, b) => Date.parse(b.updatedAt) - Date.parse(a.updatedAt))
    .map(({ messages, ...c }) => clone(c));
}
export async function getConversation(id) {
  await delay(150);
  const user = currentUser();
  const c = db.conversations.find((x) => x.id === id && x.userId === user.id);
  if (!c) throw new MockError(404, '会話が見つかりません');
  return clone(c);
}
export async function createConversation(title) {
  await delay(100);
  const user = currentUser();
  const c = { id: genId('c'), userId: user.id, title: title.slice(0, 24), createdAt: now(), updatedAt: now(), messages: [] };
  db.conversations.push(c);
  const { messages, ...rest } = c;
  return clone(rest);
}
export async function deleteConversation(id) {
  await delay(100);
  const i = db.conversations.findIndex((c) => c.id === id);
  if (i >= 0) db.conversations.splice(i, 1);
  return null;
}

/** SSE の代わりに、ステップを時間差でコールバックする */
export async function sendMessage(conversationId, content, onEvent, signal) {
  const user = currentUser();
  const conv = db.conversations.find((c) => c.id === conversationId);
  if (!conv) throw new MockError(404, '会話が見つかりません');
  conv.messages.push({ id: genId('m'), role: 'user', content, createdAt: now() });

  const { steps, message, scenarioId } = runAgent(content, user);
  for (const step of steps) {
    await delay(step.type === 'search' ? 1100 : 650);
    if (signal?.aborted) return;
    onEvent({ type: 'step', data: clone(step) });
  }
  await delay(500);
  message.createdAt = now();
  conv.messages.push(message);
  conv.updatedAt = now();
  db.logs.unshift({
    id: genId('l'), at: now(), userId: user.id, userName: user.name, department: user.department, question: content, scenarioId,
    messageId: message.id, searchCount: message.agent.searchCount, sourceCount: message.sources.length,
    result: message.inquirySuggestion ? 'no_answer' : 'resolved', feedback: null, durationMs: message.agent.durationMs, steps,
    sources: message.sources.map((s) => `${s.title} ${s.section}`),
  });
  onEvent({ type: 'answer', data: clone(message) });
}

function findMessage(messageId) {
  for (const c of db.conversations) {
    const m = c.messages.find((x) => x.id === messageId);
    if (m) return m;
  }
  return null;
}
export async function sendFeedback(messageId, feedback) {
  await delay(100);
  const m = findMessage(messageId);
  if (m) m.feedback = feedback;
  const log = db.logs.find((l) => l.messageId === messageId);
  if (log) log.feedback = feedback;
  return null;
}

// ---------- 問い合わせ ----------
export async function listMyInquiries() {
  await delay();
  const user = currentUser();
  return clone(db.inquiries.filter((q) => q.userId === user.id).sort((a, b) => Date.parse(b.createdAt) - Date.parse(a.createdAt)));
}
export async function createInquiry({ messageId, department, subject, body, context }) {
  await delay(600);
  const user = currentUser();
  const number = `INQ-2026-${String(143 + db.inquiries.length - 5).padStart(4, '0')}`;
  const inquiry = {
    id: genId('q'), number, userId: user.id, userName: user.name, userDepartment: user.department, department, subject, body,
    status: 'open', assignee: null, createdAt: now(), updatedAt: now(), context, replies: [],
  };
  db.inquiries.unshift(inquiry);
  const m = messageId && findMessage(messageId);
  if (m) m.inquiryId = inquiry.id;
  const log = db.logs.find((l) => l.messageId === messageId);
  if (log) log.result = 'inquiry';
  return clone(inquiry);
}
export async function listInquiries({ status, department, q } = {}) {
  await delay();
  const user = requireRole('admin', 'staff');
  return clone(
    db.inquiries
      .filter((x) => user.role === 'admin' || x.department === user.handlesDepartment)
      .filter((x) => !status || x.status === status)
      .filter((x) => !department || x.department === department)
      .filter((x) => !q || `${x.subject}${x.userName}${x.number}`.includes(q))
      .sort((a, b) => Date.parse(b.createdAt) - Date.parse(a.createdAt)),
  );
}
export async function getInquiry(id) {
  await delay();
  requireRole('admin', 'staff');
  const x = db.inquiries.find((i) => i.id === id);
  if (!x) throw new MockError(404, '問い合わせが見つかりません');
  return clone(x);
}
export async function updateInquiry(id, payload) {
  await delay();
  requireRole('admin', 'staff');
  const x = db.inquiries.find((i) => i.id === id);
  Object.assign(x, payload, { updatedAt: now() });
  return clone(x);
}
export async function replyInquiry(id, body) {
  await delay(400);
  const user = requireRole('admin', 'staff');
  const x = db.inquiries.find((i) => i.id === id);
  x.replies.push({ id: genId('r'), author: user.name, authorRole: user.role, body, createdAt: now() });
  if (x.status === 'open') x.status = 'in_progress';
  if (!x.assignee) x.assignee = user.name;
  x.updatedAt = now();
  return clone(x);
}

// ---------- お知らせ ----------
const isTargeted = (n, user) => n.target.type === 'all' || n.target.departments.includes(user.department);
export async function listMyNotices() {
  await delay(100);
  const user = currentUser();
  const read = db.noticeReads[user.id] ?? [];
  return clone(
    db.notices
      .filter((n) => n.status === 'published' && isTargeted(n, user))
      .sort((a, b) => Date.parse(b.publishAt) - Date.parse(a.publishAt))
      .map((n) => ({ id: n.id, title: n.title, body: n.body, priority: n.priority, publishAt: n.publishAt, read: read.includes(n.id) })),
  );
}
export async function markNoticeRead(id) {
  const user = currentUser();
  db.noticeReads[user.id] = [...new Set([...(db.noticeReads[user.id] ?? []), id])];
  return null;
}
function noticeStatus(n) {
  if (n.isDraft) return 'draft';
  const t = Date.now();
  if (n.publishAt && Date.parse(n.publishAt) > t) return 'scheduled';
  if (n.expireAt && Date.parse(n.expireAt) < t) return 'expired';
  return 'published';
}
export async function listNotices() {
  await delay();
  requireRole('admin', 'staff');
  return clone([...db.notices].sort((a, b) => Date.parse(b.createdAt) - Date.parse(a.createdAt)));
}
export async function getNotice(id) {
  await delay();
  const n = db.notices.find((x) => x.id === id);
  if (!n) throw new MockError(404, 'お知らせが見つかりません');
  return clone(n);
}
export async function createNotice(payload) {
  await delay(400);
  const user = requireRole('admin', 'staff');
  const n = { id: genId('n'), ...payload, publishAt: payload.publishAt || (payload.isDraft ? null : now()), createdBy: user.name, createdAt: now(), readCount: 0, targetCount: payload.target.type === 'all' ? 498 : payload.target.departments.length * 70 };
  n.status = noticeStatus(n);
  delete n.isDraft;
  db.notices.unshift(n);
  return clone(n);
}
export async function updateNotice(id, payload) {
  await delay(400);
  requireRole('admin', 'staff');
  const n = db.notices.find((x) => x.id === id);
  Object.assign(n, payload, { publishAt: payload.publishAt || (payload.isDraft ? null : n.publishAt ?? now()) });
  n.status = noticeStatus(n);
  delete n.isDraft;
  return clone(n);
}
export async function deleteNotice(id) {
  await delay();
  requireRole('admin', 'staff');
  db.notices.splice(db.notices.findIndex((x) => x.id === id), 1);
  return null;
}
export async function getNotificationSettings() {
  await delay();
  requireRole('admin');
  return clone(db.notificationSettings);
}
export async function saveNotificationSettings(payload) {
  await delay(500);
  requireRole('admin');
  Object.assign(db.notificationSettings, clone(payload));
  return clone(db.notificationSettings);
}

// ---------- アカウント ----------
export async function listUsers({ q, department, role, status } = {}) {
  await delay();
  requireRole('admin');
  return clone(
    db.users
      .filter((u) => !q || `${u.name}${u.email}${u.employeeId}`.includes(q))
      .filter((u) => !department || u.department === department)
      .filter((u) => !role || u.role === role)
      .filter((u) => !status || u.status === status),
  );
}
function insertUser(payload) {
  if (db.users.some((u) => u.email === payload.email)) throw new MockError(409, `${payload.email} はすでに登録されています`);
  if (db.users.some((u) => u.employeeId === payload.employeeId)) throw new MockError(409, `社員番号 ${payload.employeeId} はすでに登録されています`);
  const user = {
    id: genId('u'), employeeId: payload.employeeId, name: payload.name, email: payload.email, department: payload.department,
    role: payload.role, handlesDepartment: payload.role === 'user' ? null : payload.handlesDepartment || payload.department,
    status: payload.passwordMode === 'invite' ? 'invited' : 'active', createdAt: now(), lastLoginAt: null,
  };
  db.users.push(user);
  return user;
}
export async function createUser(payload) {
  await delay(500);
  requireRole('admin');
  return clone(insertUser(payload));
}
export async function bulkCreateUsers(rows) {
  await delay(800);
  requireRole('admin');
  const errors = [];
  let created = 0;
  rows.forEach((row, i) => {
    try {
      insertUser({ ...row, passwordMode: 'invite' });
      created++;
    } catch (e) {
      errors.push({ row: i + 1, message: e.message });
    }
  });
  return { created, errors };
}
export async function updateUser(id, payload) {
  await delay(300);
  requireRole('admin');
  const u = db.users.find((x) => x.id === id);
  Object.assign(u, payload);
  if (u.role === 'user') u.handlesDepartment = null;
  return clone(u);
}
export async function deleteUser(id) {
  await delay(300);
  const me = requireRole('admin');
  if (me.id === id) throw new MockError(400, '自分自身のアカウントは削除できません');
  db.users.splice(db.users.findIndex((u) => u.id === id), 1);
  return null;
}
export async function sendPasswordReset() {
  await delay(400);
  requireRole('admin');
  return null;
}

// ---------- ドキュメント ----------
export async function listDocuments({ q, category, department, status } = {}) {
  await delay();
  requireRole('admin', 'staff');
  return clone(
    db.documents
      .filter((d) => !q || `${d.title}${d.fileName}${d.tags.join('')}`.includes(q))
      .filter((d) => !category || d.category === category)
      .filter((d) => !department || d.department === department)
      .filter((d) => !status || d.status === status)
      .sort((a, b) => Date.parse(b.updatedAt) - Date.parse(a.updatedAt)),
  );
}
export async function getDocument(id) {
  await delay(150);
  const d = db.documents.find((x) => x.id === id);
  if (!d) throw new MockError(404, '資料が見つかりません');
  return clone({ ...d, versions: db.documentVersions[id] ?? [{ version: d.version, updatedAt: d.updatedAt, by: d.uploadedBy, note: '初回登録' }] });
}

// 取り込み処理（テキスト抽出 → チャンク分割 → ベクトル化）を時間差で進める
function simulateIndexing(doc) {
  const stages = ['extracting', 'chunking', 'embedding'];
  doc.status = 'processing';
  doc.processingStage = 'uploaded';
  stages.forEach((stage, i) => setTimeout(() => (doc.processingStage = stage), 900 * (i + 1)));
  setTimeout(() => {
    doc.status = 'indexed';
    doc.processingStage = null;
    doc.chunks = Math.max(8, Math.round(doc.size / 12000));
    doc.updatedAt = now();
  }, 900 * (stages.length + 1));
}
export async function uploadDocument(file, meta) {
  await delay(700);
  const user = requireRole('admin', 'staff');
  const ext = file.name.split('.').pop().toLowerCase();
  const doc = {
    id: genId('d'), title: meta.title || file.name.replace(/\.[^.]+$/, ''), fileName: file.name, fileType: ext, size: file.size,
    pages: Math.max(1, Math.round(file.size / 40000)), category: meta.category, department: meta.department, visibility: meta.visibility,
    tags: meta.tags, status: 'processing', chunks: 0, version: 1, effectiveDate: meta.effectiveDate, updatedAt: now(), uploadedBy: user.name,
  };
  db.documents.unshift(doc);
  simulateIndexing(doc);
  return clone(doc);
}
export async function updateDocument(id, payload) {
  await delay(300);
  requireRole('admin', 'staff');
  const d = db.documents.find((x) => x.id === id);
  Object.assign(d, payload, { updatedAt: now() });
  return clone(d);
}
export async function reindexDocument(id) {
  await delay(300);
  requireRole('admin', 'staff');
  const d = db.documents.find((x) => x.id === id);
  delete d.errorMessage;
  if (!d.size) d.size = 380000;
  simulateIndexing(d);
  return clone(d);
}
export async function deleteDocument(id) {
  await delay(300);
  requireRole('admin', 'staff');
  db.documents.splice(db.documents.findIndex((d) => d.id === id), 1);
  return null;
}

// ---------- 利用履歴 ----------
function filterLogs({ days, result, q, department } = {}) {
  const from = days ? Date.now() - Number(days) * 86400000 : 0;
  return db.logs
    .filter((l) => Date.parse(l.at) >= from)
    .filter((l) => !result || l.result === result)
    .filter((l) => !department || l.department === department)
    .filter((l) => !q || `${l.question}${l.userName}`.includes(q));
}
export async function listLogs(params) {
  await delay();
  requireRole('admin');
  return clone(filterLogs(params));
}
export async function getLogSummary(params) {
  await delay();
  requireRole('admin');
  const logs = filterLogs({ days: params?.days });
  const total = logs.length;
  const resolved = logs.filter((l) => l.result === 'resolved').length;
  const rated = logs.filter((l) => l.feedback);
  return {
    total,
    resolvedRate: total ? resolved / total : 0,
    inquiryCount: logs.filter((l) => l.result === 'inquiry').length,
    avgSearchCount: total ? logs.reduce((s, l) => s + l.searchCount, 0) / total : 0,
    avgDurationMs: total ? logs.reduce((s, l) => s + l.durationMs, 0) / total : 0,
    goodRate: rated.length ? rated.filter((l) => l.feedback === 'good').length / rated.length : 0,
    // 企画書の試算：自己解決1件あたり20分の対応時間を削減
    savedMinutes: resolved * 20,
  };
}
