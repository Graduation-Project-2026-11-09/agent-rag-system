// モック用のインメモリDB（ページを再読み込みすると初期状態に戻る）
// Flask 実装時のテーブル設計の参考にもなるよう、実データに近い形で定義している。

export const departments = ['人事部', '総務部', '経理部', '情報システム部', '営業部', '開発部', 'マーケティング部'];

export const categories = ['就業規則・規程', '人事手続き', '社会保険・福利厚生', '経費・経理', 'IT・セキュリティ', '総務・施設'];

export const users = [
  { id: 'u1', employeeId: 'E10234', name: '山田 花子', email: 'yamada@example.co.jp', department: '営業部', role: 'user', handlesDepartment: null, status: 'active', createdAt: '2024-04-01T09:00:00', lastLoginAt: '2026-10-02T08:52:00' },
  { id: 'u2', employeeId: 'E00012', name: '管理 太郎', email: 'admin@example.co.jp', department: '情報システム部', role: 'admin', handlesDepartment: '情報システム部', status: 'active', createdAt: '2023-04-01T09:00:00', lastLoginAt: '2026-10-02T09:10:00' },
  { id: 'u3', employeeId: 'E00451', name: '佐藤 美咲', email: 'sato@example.co.jp', department: '人事部', role: 'staff', handlesDepartment: '人事部', status: 'active', createdAt: '2023-10-01T09:00:00', lastLoginAt: '2026-10-01T17:31:00' },
  { id: 'u4', employeeId: 'E00502', name: '鈴木 一郎', email: 'suzuki@example.co.jp', department: '総務部', role: 'staff', handlesDepartment: '総務部', status: 'active', createdAt: '2023-10-01T09:00:00', lastLoginAt: '2026-10-01T15:02:00' },
  { id: 'u5', employeeId: 'E00611', name: '高橋 健太', email: 'takahashi@example.co.jp', department: '経理部', role: 'staff', handlesDepartment: '経理部', status: 'active', createdAt: '2024-01-15T09:00:00', lastLoginAt: '2026-09-30T11:45:00' },
  { id: 'u6', employeeId: 'E10301', name: '田中 優子', email: 'tanaka@example.co.jp', department: '開発部', role: 'user', handlesDepartment: null, status: 'active', createdAt: '2024-04-01T09:00:00', lastLoginAt: '2026-10-02T09:05:00' },
  { id: 'u7', employeeId: 'E10322', name: '伊藤 大輔', email: 'ito@example.co.jp', department: '開発部', role: 'user', handlesDepartment: null, status: 'active', createdAt: '2024-04-01T09:00:00', lastLoginAt: '2026-09-29T13:20:00' },
  { id: 'u8', employeeId: 'E10455', name: '渡辺 さくら', email: 'watanabe@example.co.jp', department: 'マーケティング部', role: 'user', handlesDepartment: null, status: 'active', createdAt: '2025-04-01T09:00:00', lastLoginAt: '2026-10-01T10:11:00' },
  { id: 'u9', employeeId: 'E10467', name: '中村 翔', email: 'nakamura@example.co.jp', department: '営業部', role: 'user', handlesDepartment: null, status: 'suspended', createdAt: '2025-04-01T09:00:00', lastLoginAt: '2026-06-30T18:00:00' },
  { id: 'u10', employeeId: 'E10498', name: '小林 未来', email: 'kobayashi@example.co.jp', department: '営業部', role: 'user', handlesDepartment: null, status: 'active', createdAt: '2025-10-01T09:00:00', lastLoginAt: '2026-10-02T08:30:00' },
  { id: 'u11', employeeId: 'E10520', name: '加藤 拓也', email: 'kato@example.co.jp', department: '情報システム部', role: 'staff', handlesDepartment: '情報システム部', status: 'active', createdAt: '2025-10-01T09:00:00', lastLoginAt: '2026-10-02T09:00:00' },
  { id: 'u12', employeeId: 'E10601', name: '吉田 結衣', email: 'yoshida@example.co.jp', department: 'マーケティング部', role: 'user', handlesDepartment: null, status: 'invited', createdAt: '2026-09-28T14:00:00', lastLoginAt: null },
  { id: 'u13', employeeId: 'E10602', name: '山本 蓮', email: 'yamamoto@example.co.jp', department: '開発部', role: 'user', handlesDepartment: null, status: 'invited', createdAt: '2026-09-28T14:00:00', lastLoginAt: null },
];

// visibility: { type: 'all' } または { type: 'departments', departments: [...] }
export const documents = [
  { id: 'd1', title: '就業規則', fileName: 'shugyo_kisoku_2026.pdf', fileType: 'pdf', size: 1843200, pages: 48, category: '就業規則・規程', department: '人事部', visibility: { type: 'all' }, tags: ['休暇', '勤務', '兼業'], status: 'indexed', chunks: 212, version: 5, effectiveDate: '2026-04-01', updatedAt: '2026-03-25T10:00:00', uploadedBy: '佐藤 美咲' },
  { id: 'd2', title: '慶弔見舞金規程', fileName: 'keicho_mimaikin.pdf', fileType: 'pdf', size: 312000, pages: 6, category: '社会保険・福利厚生', department: '総務部', visibility: { type: 'all' }, tags: ['結婚', '出産', '弔事'], status: 'indexed', chunks: 24, version: 3, effectiveDate: '2025-04-01', updatedAt: '2025-03-18T15:20:00', uploadedBy: '鈴木 一郎' },
  { id: 'd3', title: '人事手続きマニュアル（氏名・住所・家族の変更）', fileName: 'jinji_tetsuzuki_manual.docx', fileType: 'docx', size: 520000, pages: 22, category: '人事手続き', department: '人事部', visibility: { type: 'all' }, tags: ['氏名変更', '住所変更', '扶養'], status: 'indexed', chunks: 86, version: 7, effectiveDate: '2026-07-01', updatedAt: '2026-06-20T11:30:00', uploadedBy: '佐藤 美咲' },
  { id: 'd4', title: '社会保険・扶養手続きガイド', fileName: 'shakai_hoken_guide.pdf', fileType: 'pdf', size: 980000, pages: 18, category: '社会保険・福利厚生', department: '人事部', visibility: { type: 'all' }, tags: ['健康保険', '扶養', '年金'], status: 'indexed', chunks: 74, version: 4, effectiveDate: '2026-04-01', updatedAt: '2026-04-02T09:15:00', uploadedBy: '佐藤 美咲' },
  { id: 'd5', title: '通勤手当規程', fileName: 'tsukin_teate.pdf', fileType: 'pdf', size: 210000, pages: 5, category: '経費・経理', department: '経理部', visibility: { type: 'all' }, tags: ['通勤', '手当'], status: 'indexed', chunks: 18, version: 2, effectiveDate: '2025-10-01', updatedAt: '2025-09-12T16:40:00', uploadedBy: '高橋 健太' },
  { id: 'd6', title: '経費精算マニュアル', fileName: 'keihi_seisan_manual.pdf', fileType: 'pdf', size: 1320000, pages: 26, category: '経費・経理', department: '経理部', visibility: { type: 'all' }, tags: ['経費', '領収書', '出張'], status: 'indexed', chunks: 98, version: 6, effectiveDate: '2026-04-01', updatedAt: '2026-03-30T13:00:00', uploadedBy: '高橋 健太' },
  { id: 'd7', title: '情報セキュリティポリシー', fileName: 'security_policy.pdf', fileType: 'pdf', size: 760000, pages: 30, category: 'IT・セキュリティ', department: '情報システム部', visibility: { type: 'all' }, tags: ['セキュリティ', 'パスワード'], status: 'indexed', chunks: 120, version: 3, effectiveDate: '2026-01-01', updatedAt: '2025-12-15T10:10:00', uploadedBy: '加藤 拓也' },
  { id: 'd8', title: 'PC・アカウント利用ガイド', fileName: 'pc_account_guide.pptx', fileType: 'pptx', size: 2400000, pages: 34, category: 'IT・セキュリティ', department: '情報システム部', visibility: { type: 'all' }, tags: ['PC', 'パスワード', 'VPN'], status: 'indexed', chunks: 64, version: 8, effectiveDate: '2026-08-01', updatedAt: '2026-07-28T17:45:00', uploadedBy: '加藤 拓也' },
  { id: 'd9', title: '育児・介護休業規程', fileName: 'ikuji_kaigo_kitei.pdf', fileType: 'pdf', size: 640000, pages: 16, category: '就業規則・規程', department: '人事部', visibility: { type: 'all' }, tags: ['育休', '産休', '介護'], status: 'indexed', chunks: 58, version: 4, effectiveDate: '2025-10-01', updatedAt: '2025-09-20T09:00:00', uploadedBy: '佐藤 美咲' },
  { id: 'd10', title: '人事評価運用マニュアル（評価者向け）', fileName: 'hyoka_manual.pdf', fileType: 'pdf', size: 880000, pages: 20, category: '人事手続き', department: '人事部', visibility: { type: 'departments', departments: ['人事部'] }, tags: ['評価'], status: 'indexed', chunks: 70, version: 2, effectiveDate: '2026-04-01', updatedAt: '2026-03-10T14:00:00', uploadedBy: '佐藤 美咲' },
  { id: 'd11', title: '2026年度 給与改定資料', fileName: 'kyuyo_kaitei_2026.xlsx', fileType: 'xlsx', size: 150000, pages: 4, category: '経費・経理', department: '人事部', visibility: { type: 'departments', departments: ['人事部', '経理部'] }, tags: ['給与'], status: 'processing', chunks: 0, version: 1, effectiveDate: '2026-10-01', updatedAt: '2026-10-02T08:40:00', uploadedBy: '佐藤 美咲' },
  { id: 'd12', title: 'リモートワーク規程', fileName: 'remote_work.pdf', fileType: 'pdf', size: 0, pages: 0, category: '就業規則・規程', department: '総務部', visibility: { type: 'all' }, tags: ['在宅勤務'], status: 'error', errorMessage: 'PDFのテキストを抽出できませんでした（画像のみのPDFの可能性があります）', chunks: 0, version: 1, effectiveDate: '2026-10-01', updatedAt: '2026-10-01T18:05:00', uploadedBy: '鈴木 一郎' },
  { id: 'd13', title: 'オフィス利用・来客対応ガイド', fileName: 'office_guide.pdf', fileType: 'pdf', size: 430000, pages: 12, category: '総務・施設', department: '総務部', visibility: { type: 'all' }, tags: ['会議室', '来客'], status: 'indexed', chunks: 40, version: 2, effectiveDate: '2025-07-01', updatedAt: '2025-06-25T12:00:00', uploadedBy: '鈴木 一郎' },
];

// 資料ごとの代表的なバージョン履歴（詳細画面用）
export const documentVersions = {
  d1: [
    { version: 5, updatedAt: '2026-03-25T10:00:00', by: '佐藤 美咲', note: '2026年4月改定（特別休暇の日数を変更）' },
    { version: 4, updatedAt: '2025-03-20T10:00:00', by: '佐藤 美咲', note: '兼業規定を追加' },
    { version: 3, updatedAt: '2024-03-21T10:00:00', by: '佐藤 美咲', note: '年次改定' },
  ],
  d3: [
    { version: 7, updatedAt: '2026-06-20T11:30:00', by: '佐藤 美咲', note: '人事システム刷新に伴う手順の更新' },
    { version: 6, updatedAt: '2025-11-02T11:30:00', by: '佐藤 美咲', note: '旧姓使用の手続きを追記' },
  ],
};

export const notices = [
  { id: 'n1', title: '年末調整の書類提出期限について（11月14日締切）', body: '今年度の年末調整書類は人事システムから11月14日（金）までに提出してください。\n提出方法は「人事手続きマニュアル」第6章を参照してください。', priority: 'important', target: { type: 'all' }, channels: ['in_app', 'email'], publishAt: '2026-10-01T09:00:00', expireAt: '2026-11-14T23:59:00', status: 'published', createdBy: '佐藤 美咲', createdAt: '2026-09-29T10:00:00', readCount: 312, targetCount: 498 },
  { id: 'n2', title: '就業規則（2026年4月改定版）を登録しました', body: '特別休暇の日数などが変更されています。AIチャットでも最新の内容で回答されます。', priority: 'normal', target: { type: 'all' }, channels: ['in_app'], publishAt: '2026-09-25T09:00:00', expireAt: null, status: 'published', createdBy: '管理 太郎', createdAt: '2026-09-25T08:50:00', readCount: 401, targetCount: 498 },
  { id: 'n3', title: '10月5日(日) システムメンテナンスのお知らせ', body: '10月5日 2:00〜6:00 の間、社内ナビAIを含む社内システムが利用できません。', priority: 'normal', target: { type: 'all' }, channels: ['in_app', 'email'], publishAt: '2026-09-30T12:00:00', expireAt: '2026-10-05T06:00:00', status: 'published', createdBy: '加藤 拓也', createdAt: '2026-09-30T11:00:00', readCount: 220, targetCount: 498 },
  { id: 'n4', title: '営業部向け：経費精算の締め日変更', body: '11月より営業部の経費精算締め日が毎月20日に変更になります。', priority: 'important', target: { type: 'departments', departments: ['営業部'] }, channels: ['in_app', 'email'], publishAt: '2026-10-10T09:00:00', expireAt: null, status: 'scheduled', createdBy: '高橋 健太', createdAt: '2026-10-01T16:00:00', readCount: 0, targetCount: 120 },
  { id: 'n5', title: 'ストレスチェック実施のご案内（下書き）', body: '今年度のストレスチェックを11月に実施します。詳細は追ってご連絡します。', priority: 'normal', target: { type: 'all' }, channels: ['in_app'], publishAt: null, expireAt: null, status: 'draft', createdBy: '佐藤 美咲', createdAt: '2026-10-01T13:00:00', readCount: 0, targetCount: 498 },
  { id: 'n6', title: '夏季休暇の取得について', body: '夏季休暇は9月末までに取得してください。', priority: 'normal', target: { type: 'all' }, channels: ['in_app'], publishAt: '2026-07-01T09:00:00', expireAt: '2026-09-30T23:59:00', status: 'expired', createdBy: '佐藤 美咲', createdAt: '2026-06-28T10:00:00', readCount: 470, targetCount: 498 },
];

// 利用者ごとの既読状態
export const noticeReads = { u1: ['n2'] };

export const notificationSettings = {
  events: [
    { key: 'inquiry_created', label: '新しい問い合わせを受け付けたとき', description: '担当部署の担当者に通知します', inApp: true, email: true },
    { key: 'inquiry_replied', label: '問い合わせに回答があったとき', description: '問い合わせた利用者に通知します', inApp: true, email: true },
    { key: 'inquiry_overdue', label: '問い合わせが3営業日以上未対応のとき', description: '担当部署と管理者に通知します', inApp: true, email: false },
    { key: 'document_indexed', label: '資料の取り込みが完了したとき', description: 'アップロードした担当者に通知します', inApp: true, email: false },
    { key: 'document_failed', label: '資料の取り込みに失敗したとき', description: 'アップロードした担当者と管理者に通知します', inApp: true, email: true },
    { key: 'low_rating', label: 'AIの回答に低評価が付いたとき', description: '管理者に通知します（資料改善の参考）', inApp: true, email: false },
  ],
  departmentContacts: [
    { department: '人事部', email: 'jinji@example.co.jp' },
    { department: '総務部', email: 'somu@example.co.jp' },
    { department: '経理部', email: 'keiri@example.co.jp' },
    { department: '情報システム部', email: 'it-help@example.co.jp' },
  ],
  weeklyReport: { enabled: true, dayOfWeek: 'mon', recipients: 'admin@example.co.jp' },
};

export const inquiries = [
  {
    id: 'q1', number: 'INQ-2026-0142', userId: 'u6', userName: '田中 優子', userDepartment: '開発部', department: '人事部',
    subject: '時短勤務の延長申請について', body: '人事部 ご担当者様\n\n開発部の田中です。\n現在、子どもが3歳になるまで時短勤務を利用していますが、小学校入学まで延長できるか確認させてください。\n\n■ 確認済みの社内資料\n・育児・介護休業規程 第18条（短時間勤務）\n\n■ 不明な点\n・3歳以降の延長が認められる条件\n\nよろしくお願いいたします。',
    status: 'open', assignee: null, createdAt: '2026-10-02T08:45:00', updatedAt: '2026-10-02T08:45:00',
    context: { question: '時短勤務は子どもが何歳まで使える？延長はできる？', sources: ['育児・介護休業規程 第18条'], aiAnswerSummary: '規程上は3歳までの短時間勤務が定められている。延長の可否は資料に記載なし。' },
    replies: [],
  },
  {
    id: 'q2', number: 'INQ-2026-0141', userId: 'u10', userName: '小林 未来', userDepartment: '営業部', department: '経理部',
    subject: '海外出張時の日当の扱い', body: '経理部 ご担当者様\n\n営業部の小林です。\n来月のシンガポール出張について、日当の金額と精算方法を教えてください。\n\n■ 確認済みの社内資料\n・経費精算マニュアル 第4章\n\nよろしくお願いいたします。',
    status: 'in_progress', assignee: '高橋 健太', createdAt: '2026-10-01T15:20:00', updatedAt: '2026-10-01T16:05:00',
    context: { question: '海外出張の日当っていくら？', sources: ['経費精算マニュアル 4.3 出張旅費'], aiAnswerSummary: '国内出張の日当は記載あり。海外出張は「別途定める」とのみ記載。' },
    replies: [{ id: 'r1', author: '高橋 健太', authorRole: 'staff', body: '確認しますので少々お待ちください。海外出張旅費規程を別途お送りします。', createdAt: '2026-10-01T16:05:00' }],
  },
  {
    id: 'q3', number: 'INQ-2026-0138', userId: 'u1', userName: '山田 花子', userDepartment: '営業部', department: '情報システム部',
    subject: '社用スマートフォンの機種変更について', body: '情報システム部 ご担当者様\n\n営業部の山田です。\n社用スマートフォンの画面が割れてしまったため、修理または機種変更の手続きを教えてください。\n\nよろしくお願いいたします。',
    status: 'resolved', assignee: '加藤 拓也', createdAt: '2026-09-26T10:12:00', updatedAt: '2026-09-26T14:30:00',
    context: { question: '社用スマホの画面が割れた。どうすればいい？', sources: ['PC・アカウント利用ガイド 7章 モバイル端末'], aiAnswerSummary: '紛失時の手順は記載あり。破損時の修理手順は記載なし。' },
    replies: [{ id: 'r2', author: '加藤 拓也', authorRole: 'staff', body: '代替機を本日中にお渡しします。情報システム部（3F）までお越しください。修理申請はこちらで行います。', createdAt: '2026-09-26T14:30:00' }],
  },
  {
    id: 'q4', number: 'INQ-2026-0135', userId: 'u8', userName: '渡辺 さくら', userDepartment: 'マーケティング部', department: '総務部',
    subject: '大会議室の土日利用について', body: '総務部 ご担当者様\n\nマーケティング部の渡辺です。\n11月のイベント準備で大会議室を土曜日に利用したいのですが、申請方法を教えてください。\n\nよろしくお願いいたします。',
    status: 'resolved', assignee: '鈴木 一郎', createdAt: '2026-09-24T11:00:00', updatedAt: '2026-09-25T09:20:00',
    context: { question: '会議室って土日も使える？', sources: ['オフィス利用・来客対応ガイド 2章'], aiAnswerSummary: '平日の予約方法は記載あり。休日利用は記載なし。' },
    replies: [{ id: 'r3', author: '鈴木 一郎', authorRole: 'staff', body: '休日利用申請書を総務部までご提出ください。警備会社への連絡はこちらで行います。', createdAt: '2026-09-25T09:20:00' }],
  },
  {
    id: 'q5', number: 'INQ-2026-0130', userId: 'u7', userName: '伊藤 大輔', userDepartment: '開発部', department: '人事部',
    subject: '副業（技術顧問）の許可申請について', body: '人事部 ご担当者様\n\n開発部の伊藤です。\n副業で他社の技術顧問を行いたいと考えています。許可の基準と申請書について教えてください。\n\nよろしくお願いいたします。',
    status: 'in_progress', assignee: '佐藤 美咲', createdAt: '2026-09-20T17:40:00', updatedAt: '2026-09-22T10:00:00',
    context: { question: '副業ってしてもいい？', sources: ['就業規則 第45条'], aiAnswerSummary: '事前許可制であることは記載あり。基準・様式は記載なし。' },
    replies: [{ id: 'r4', author: '佐藤 美咲', authorRole: 'staff', body: '申請書をメールでお送りしました。競業にあたらないか確認のため、顧問先の事業内容を追記して再提出をお願いします。', createdAt: '2026-09-22T10:00:00' }],
  },
];

export const conversations = []; // seed.js で初期化
export const logs = []; // seed.js で初期化
