// 画面から呼び出す API 関数の一覧。
// 既定では Flask の /api/* を呼び出す。VITE_USE_MOCK=true のときは src/mocks/handlers.js が応答する。
// エンドポイント仕様は docs/api-spec.md を参照。
import { USE_MOCK, http, streamSSE } from './client';
import * as mock from '../mocks/handlers';

const pick = (mockFn, realFn) => (USE_MOCK ? mockFn : realFn);

// ---------- 認証 ----------
// 認証は実装済みのため、モック動作中でも Flask の API を使う（VITE_USE_REAL_AUTH=false でモックに戻せる）。
const USE_REAL_AUTH = import.meta.env.VITE_USE_REAL_AUTH !== 'false';

/**
 * 他の画面はまだモックで動くため、Flask でログインした利用者をモック側にも反映する。
 *
 * @param {Object|null} user Flask の API が返した利用者。
 * @return {Promise<Object|null>} 受け取った利用者をそのまま返す。
 */
async function syncMockSession(user) {
  if (USE_MOCK) {
    if (user) await mock.login(user.email, 'sync').catch(() => {});
    else await mock.logout();
  }
  return user;
}

const realAuthApi = {
  login: (email, password) => http.post('/auth/login', { email, password }).then(syncMockSession),
  logout: () => http.post('/auth/logout').then(() => syncMockSession(null)),
  me: () => http.get('/auth/me').then(syncMockSession),
};

export const authApi = USE_REAL_AUTH
  ? realAuthApi
  : { login: mock.login, logout: mock.logout, me: mock.me };

// ---------- マスタ ----------
export const masterApi = {
  getDepartments: pick(mock.getDepartments, () => http.get('/departments')),
  getCategories: pick(mock.getCategories, () => http.get('/document-categories')),
};

// ---------- チャット ----------
export const chatApi = {
  listConversations: pick(mock.listConversations, () => http.get('/conversations')),
  getConversation: pick(mock.getConversation, (id) => http.get(`/conversations/${id}`)),
  createConversation: pick(mock.createConversation, (title) => http.post('/conversations', { title })),
  deleteConversation: pick(mock.deleteConversation, (id) => http.delete(`/conversations/${id}`)),
  /**
   * 質問を送信し、Agent の処理過程をストリーミングで受け取る。
   * onEvent には { type: 'step' | 'answer' | 'error', data } が順に渡される。
   */
  sendMessage: pick(mock.sendMessage, (conversationId, content, onEvent, signal) =>
    streamSSE(`/conversations/${conversationId}/messages`, { content }, onEvent, signal),
  ),
  sendFeedback: pick(mock.sendFeedback, (messageId, feedback) =>
    http.post(`/messages/${messageId}/feedback`, { feedback }),
  ),
};

// ---------- 問い合わせ ----------
export const inquiryApi = {
  listMine: pick(mock.listMyInquiries, () => http.get('/inquiries/mine')),
  create: pick(mock.createInquiry, (payload) => http.post('/inquiries', payload)),
  // 管理者・部署担当者向け
  list: pick(mock.listInquiries, (params) => http.get('/admin/inquiries', { params })),
  get: pick(mock.getInquiry, (id) => http.get(`/admin/inquiries/${id}`)),
  update: pick(mock.updateInquiry, (id, payload) => http.patch(`/admin/inquiries/${id}`, payload)),
  reply: pick(mock.replyInquiry, (id, body) => http.post(`/admin/inquiries/${id}/replies`, { body })),
};

// ---------- お知らせ ----------
export const noticeApi = {
  listMine: pick(mock.listMyNotices, () => http.get('/notices')),
  markRead: pick(mock.markNoticeRead, (id) => http.post(`/notices/${id}/read`)),
  // 管理者向け
  list: pick(mock.listNotices, () => http.get('/admin/notices')),
  get: pick(mock.getNotice, (id) => http.get(`/admin/notices/${id}`)),
  create: pick(mock.createNotice, (payload) => http.post('/admin/notices', payload)),
  update: pick(mock.updateNotice, (id, payload) => http.put(`/admin/notices/${id}`, payload)),
  remove: pick(mock.deleteNotice, (id) => http.delete(`/admin/notices/${id}`)),
  getSettings: pick(mock.getNotificationSettings, () => http.get('/admin/notification-settings')),
  saveSettings: pick(mock.saveNotificationSettings, (payload) => http.put('/admin/notification-settings', payload)),
};

// ---------- アカウント（管理者） ----------
export const userApi = {
  list: pick(mock.listUsers, (params) => http.get('/admin/users', { params })),
  create: pick(mock.createUser, (payload) => http.post('/admin/users', payload)),
  bulkCreate: pick(mock.bulkCreateUsers, (rows, password) => http.post('/admin/users/bulk', { users: rows, password })),
  // payload に password を入れるとパスワードの再設定になる
  update: pick(mock.updateUser, (id, payload) => http.patch(`/admin/users/${id}`, payload)),
  remove: pick(mock.deleteUser, (id) => http.delete(`/admin/users/${id}`)),
};

// ---------- ドキュメント（管理者） ----------
export const documentApi = {
  list: pick(mock.listDocuments, (params) => http.get('/admin/documents', { params })),
  get: pick(mock.getDocument, (id) => http.get(`/admin/documents/${id}`)),
  /** files: File[], meta: { category, department, visibility, tags, effectiveDate } */
  upload: pick(mock.uploadDocument, (file, meta) => {
    const form = new FormData();
    form.append('file', file);
    form.append('meta', JSON.stringify(meta));
    return http.post('/admin/documents', form);
  }),
  update: pick(mock.updateDocument, (id, payload) => http.patch(`/admin/documents/${id}`, payload)),
  reindex: pick(mock.reindexDocument, (id) => http.post(`/admin/documents/${id}/reindex`)),
  remove: pick(mock.deleteDocument, (id) => http.delete(`/admin/documents/${id}`)),
  // 利用者が根拠資料を開くとき
  getSource: pick(mock.getDocument, (id) => http.get(`/documents/${id}`)),
};

// ---------- 利用履歴（管理者） ----------
export const logApi = {
  list: pick(mock.listLogs, (params) => http.get('/admin/logs', { params })),
  summary: pick(mock.getLogSummary, (params) => http.get('/admin/logs/summary', { params })),
};
