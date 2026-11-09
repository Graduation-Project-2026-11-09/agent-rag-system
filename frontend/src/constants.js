// 画面表示用のラベル定義（Flask 側の値と合わせる）

export const ROLES = {
  user: { label: '一般利用者', description: 'AIチャットの利用、問い合わせの作成ができます' },
  staff: { label: '部署担当者', description: '担当部署あての問い合わせに対応できます（人事・総務・経理・情シスなど）' },
  admin: { label: '管理者', description: 'アカウント・資料・お知らせなど、すべての管理機能を利用できます' },
};

export const USER_STATUS = {
  active: { label: '有効', tone: 'green' },
  invited: { label: '招待中', tone: 'blue' },
  suspended: { label: '利用停止', tone: 'gray' },
};

export const DOC_STATUS = {
  indexed: { label: '検索可能', tone: 'green' },
  processing: { label: '処理中', tone: 'blue' },
  error: { label: 'エラー', tone: 'red' },
};

export const INQUIRY_STATUS = {
  open: { label: '未対応', tone: 'red' },
  in_progress: { label: '対応中', tone: 'yellow' },
  resolved: { label: '解決済み', tone: 'green' },
};

export const NOTICE_PRIORITY = {
  normal: { label: '通常', tone: 'gray' },
  important: { label: '重要', tone: 'red' },
};

export const NOTICE_STATUS = {
  draft: { label: '下書き', tone: 'gray' },
  scheduled: { label: '配信予約', tone: 'blue' },
  published: { label: '配信中', tone: 'green' },
  expired: { label: '掲載終了', tone: 'gray' },
};

export const LOG_RESULT = {
  resolved: { label: '自己解決', tone: 'green' },
  inquiry: { label: '問い合わせ', tone: 'yellow' },
  no_answer: { label: '回答不可', tone: 'red' },
};

export const AGENT_STEP_LABEL = {
  analyze: '質問分析',
  plan: '検索戦略',
  search: '検索',
  evaluate: '充足度評価',
  generate: '回答生成',
};

// チャット初期画面の質問例
export const SUGGESTED_QUESTIONS = [
  '結婚したんだけど会社で必要な手続きってある？',
  '引越しをしたら何を申請すればいい？',
  'パスワードを忘れてログインできない',
  '副業ってしてもいいの？',
];
