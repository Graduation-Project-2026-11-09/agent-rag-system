// Agentic RAG の動作を再現するダミー実装。
// 実際は Flask 側で「質問分析 → 検索語の展開 → 検索 → 充足度評価 → (必要なら)再検索 → 回答生成」を行い、
// 各ステップを SSE の step イベントとして送信する想定。ここではキーワードでシナリオを切り替える。
import { documents } from './db';

const SCENARIOS = [
  {
    id: 'marriage',
    match: /結婚|婚姻|入籍/,
    keyword: '結婚',
    intent: '結婚に伴って必要になる社内手続きを網羅的に知りたい',
    viewpoints: ['氏名の変更', '家族（扶養）の追加', '社会保険・税', '休暇・祝金などの慶弔制度'],
    rounds: [
      {
        queries: ['婚姻 届出', '氏名変更 手続き', '扶養 追加', '社会保険 被扶養者', '慶弔 結婚祝金'],
        hits: [['d3', 0.91, '3.2 氏名変更'], ['d4', 0.88, '2.1 被扶養者の認定基準'], ['d2', 0.84, '第5条 結婚祝金'], ['d3', 0.71, '3.4 住所変更']],
        sufficient: false,
        evaluation: '結婚休暇（特別休暇）の日数・取得期限に関する情報が不足しています。別の検索語で追加検索します。',
      },
      {
        queries: ['特別休暇 結婚', '結婚休暇 取得期限'],
        hits: [['d1', 0.93, '第32条 特別休暇']],
        sufficient: true,
        evaluation: '手続き・制度の4観点すべてについて根拠となる情報が揃いました。',
      },
    ],
    answer: `ご結婚おめでとうございます。結婚に伴って必要となる主な社内手続きは次の4つです。

### 1. 氏名変更（姓が変わる場合）
- 人事システムから「氏名変更届」を提出してください。業務上の旧姓使用も選択できます [1]
- メールアドレス・社員証・名刺の変更は、届出の承認後に自動で手配されます [1]

### 2. 扶養の追加（配偶者を扶養に入れる場合）
- 配偶者の年収見込みが **130万円未満** であれば、健康保険の被扶養者として申請できます [2]
- 婚姻日から **5日以内** に「被扶養者（異動）届」と課税証明書などを提出してください [2]

### 3. 住所・社会保険・税
- 住所が変わる場合は「住所変更届」と通勤手当の再申請が必要です [3]
- 年末調整で配偶者控除・配偶者特別控除の対象となる場合があります [2]

### 4. 慶弔制度
- 結婚休暇として **連続5日間** の特別休暇（有給）を、婚姻日から6か月以内に取得できます [4]
- 結婚祝金 **30,000円** が支給されます。婚姻日から3か月以内に「慶弔金申請書」を提出してください [5]`,
    sources: [
      ['d3', '3.2 氏名変更', 8, '氏名に変更があった場合は、人事システムの「氏名変更届」により速やかに届け出ること。業務上の旧姓使用を希望する場合は、届出時に「旧姓使用」を選択する。'],
      ['d4', '2.1 被扶養者の認定基準', 4, '被扶養者として認定を受けるには、年間収入が130万円未満であること。異動が生じた日から5日以内に被扶養者（異動）届を提出すること。'],
      ['d3', '3.4 住所変更', 11, '住所を変更した場合は、住所変更届を提出するとともに、通勤経路に変更がある場合は通勤手当の再申請を行うこと。'],
      ['d1', '第32条（特別休暇）', 15, '本人が結婚するときは、婚姻日から6か月以内に連続5日間の特別休暇を与える。特別休暇は有給とする。'],
      ['d2', '第5条（結婚祝金）', 2, '従業員が結婚したときは、結婚祝金として30,000円を支給する。申請は婚姻日から3か月以内に慶弔金申請書により行う。'],
    ],
    nextSteps: [
      { title: '氏名変更届の提出', description: '人事システム > 各種届出 > 氏名変更', department: '人事部', deadline: '速やかに' },
      { title: '被扶養者（異動）届の提出', description: '課税証明書・婚姻の事実が確認できる書類を添付', department: '人事部', deadline: '婚姻日から5日以内' },
      { title: '慶弔金申請書の提出', description: '総務ポータル > 申請書ダウンロード', department: '総務部', deadline: '婚姻日から3か月以内' },
      { title: '結婚休暇の取得申請', description: '勤怠システムで「特別休暇（結婚）」を選択', department: '人事部', deadline: '婚姻日から6か月以内' },
    ],
    inquiry: null,
  },
  {
    id: 'moving',
    match: /引越|引っ越|住所|転居/,
    keyword: '引越し',
    intent: '引越しに伴う社内での届出・手当の変更を知りたい',
    viewpoints: ['住所変更の届出', '通勤手当の変更', '社会保険の住所変更'],
    rounds: [
      {
        queries: ['住所変更 届出', '通勤手当 変更', '転居 社会保険'],
        hits: [['d3', 0.92, '3.4 住所変更'], ['d5', 0.89, '第6条 経路変更'], ['d4', 0.74, '5.2 住所変更の連携']],
        sufficient: true,
        evaluation: '1回目の検索で必要な情報が揃ったため、追加検索は不要と判断しました。',
      },
    ],
    answer: `引越しをした場合に必要な社内手続きは次のとおりです。

1. **住所変更届の提出** — 転居後14日以内に人事システムから提出してください [1]
2. **通勤手当の再申請** — 通勤経路が変わる場合は、経路変更日から1か月以内に申請してください。申請が遅れると遡っての支給は最大1か月分となります [2]
3. **社会保険の住所変更** — 住所変更届の内容が自動で連携されるため、個別の手続きは不要です [3]`,
    sources: [
      ['d3', '3.4 住所変更', 11, '住所を変更した場合は、転居後14日以内に人事システムの住所変更届により届け出ること。'],
      ['d5', '第6条（経路変更）', 3, '通勤経路に変更が生じた場合は、変更日から1か月以内に申請すること。申請が遅れた場合の遡及支給は1か月分を限度とする。'],
      ['d4', '5.2 住所変更の連携', 15, '人事システムで受理した住所変更は、健康保険・厚生年金の届出に自動で反映される。'],
    ],
    nextSteps: [
      { title: '住所変更届の提出', description: '人事システム > 各種届出 > 住所変更', department: '人事部', deadline: '転居後14日以内' },
      { title: '通勤手当の再申請', description: '経費システム > 通勤手当申請', department: '経理部', deadline: '経路変更日から1か月以内' },
    ],
    inquiry: null,
  },
  {
    id: 'password',
    match: /パスワード|ログインでき|ロック|PC|パソコン/,
    keyword: 'パスワード',
    intent: '社内システムにログインできない問題を自分で解決したい',
    viewpoints: ['パスワードの再設定方法', 'アカウントロックの解除', '問い合わせ先'],
    rounds: [
      {
        queries: ['パスワード 再設定', 'アカウント ロック 解除', 'ログイン できない'],
        hits: [['d8', 0.94, '2.3 パスワードを忘れたとき'], ['d8', 0.86, '2.4 アカウントロック'], ['d7', 0.62, '第12条 パスワード管理']],
        sufficient: true,
        evaluation: '自己解決の手順と、解決できない場合の連絡先が揃いました。',
      },
    ],
    answer: `パスワードを忘れた場合は、次の手順でご自身で再設定できます。

1. ログイン画面の「パスワードをお忘れの方」をクリック [1]
2. 社員番号を入力し、登録済みの携帯電話に届く認証コードを入力 [1]
3. 新しいパスワードを設定（12文字以上・英大文字/小文字/数字を含む） [2]

なお、5回連続で入力を誤るとアカウントが **30分間ロック** されます。30分経過しても解除されない場合は、情報システム部ヘルプデスク（内線 1234）へ連絡してください [3]`,
    sources: [
      ['d8', '2.3 パスワードを忘れたとき', 6, 'ログイン画面の「パスワードをお忘れの方」から、社員番号と認証コードによりパスワードを再設定できる。'],
      ['d7', '第12条（パスワード管理）', 9, 'パスワードは12文字以上とし、英大文字・英小文字・数字をそれぞれ1文字以上含めること。'],
      ['d8', '2.4 アカウントロック', 7, '5回連続で認証に失敗した場合、アカウントは30分間ロックされる。解除されない場合はヘルプデスク（内線1234）へ連絡する。'],
    ],
    nextSteps: [],
    inquiry: null,
  },
  {
    id: 'expense',
    match: /経費|精算|領収書|立替/,
    keyword: '経費精算',
    intent: '経費精算の締め日と提出方法を知りたい',
    viewpoints: ['締め日・支払日', '必要書類（領収書）', '申請方法'],
    rounds: [
      {
        queries: ['経費精算 締め日', '経費 支払日', '領収書 提出'],
        hits: [['d6', 0.9, '2.1 締め日と支払日'], ['d6', 0.85, '3.2 領収書の取扱い']],
        sufficient: false,
        evaluation: '部署ごとの締め日の例外があるか不明です。お知らせ・規程を追加検索します。',
      },
      {
        queries: ['締め日 変更 部署', '経費精算 例外'],
        hits: [['d6', 0.77, '2.2 締め日の例外']],
        sufficient: true,
        evaluation: '例外規定も確認できました。',
      },
    ],
    answer: `経費精算の締め日と提出方法は次のとおりです。

- **締め日**：毎月末日。翌月15日に給与口座へ振り込まれます [1]
- **領収書**：経費システムに画像をアップロードし、原本は月末までに経理部へ提出してください（電子領収書は原本不要） [2]
- **例外**：部署ごとに締め日が異なる場合はお知らせで案内されます。営業部は **11月から毎月20日締め** に変更予定です [3]`,
    sources: [
      ['d6', '2.1 締め日と支払日', 5, '経費精算の締め日は毎月末日とし、翌月15日に給与振込口座へ支払う。'],
      ['d6', '3.2 領収書の取扱い', 9, '領収書は画像を経費システムに添付し、紙の原本は月末までに経理部へ提出する。電子領収書の場合は原本の提出を要しない。'],
      ['d6', '2.2 締め日の例外', 6, '業務の都合により部署単位で締め日を変更する場合は、経理部が別途通知する。'],
    ],
    nextSteps: [
      { title: '経費システムで精算申請', description: '経費システム > 新規申請 > 領収書画像を添付', department: '経理部', deadline: '毎月末日' },
    ],
    inquiry: null,
  },
  {
    id: 'childcare',
    match: /育休|育児|出産|産休|子ども|子供/,
    keyword: '出産・育児',
    intent: '出産・育児に関する休業制度と手続きを知りたい',
    viewpoints: ['産前産後休業', '育児休業', '給付金・社会保険', '慶弔金'],
    rounds: [
      {
        queries: ['産前産後休業', '育児休業 申出', '出産 社会保険'],
        hits: [['d9', 0.93, '第3条 育児休業の申出'], ['d9', 0.87, '第2条 産前産後休業'], ['d4', 0.8, '4.1 出産・育児に関する給付']],
        sufficient: false,
        evaluation: '会社独自の出産祝金について情報が不足しています。慶弔制度を追加検索します。',
      },
      {
        queries: ['出産祝金', '慶弔 出産'],
        hits: [['d2', 0.9, '第6条 出産祝金']],
        sufficient: true,
        evaluation: '休業・給付・慶弔の情報が揃いました。',
      },
    ],
    answer: `出産・育児に関する主な制度と手続きは次のとおりです。

- **産前産後休業**：出産予定日の6週間前から、出産後8週間まで取得できます [1]
- **育児休業**：原則、子どもが1歳になるまで取得できます。開始予定日の **1か月前まで** に申し出てください [2]
- **給付・社会保険**：休業中は出産手当金・育児休業給付金の対象となり、社会保険料は免除されます [3]
- **出産祝金**：1子につき **20,000円** が支給されます [4]`,
    sources: [
      ['d9', '第2条（産前産後休業）', 2, '6週間（多胎妊娠の場合は14週間）以内に出産予定の者が請求したとき、及び産後8週間を経過しない者は就業させない。'],
      ['d9', '第3条（育児休業の申出）', 3, '育児休業を希望する者は、休業開始予定日の1か月前までに育児休業申出書を提出する。'],
      ['d4', '4.1 出産・育児に関する給付', 12, '産前産後休業・育児休業期間中は、申出により健康保険料・厚生年金保険料が免除される。'],
      ['d2', '第6条（出産祝金）', 2, '従業員又はその配偶者が出産したときは、1子につき20,000円を支給する。'],
    ],
    nextSteps: [
      { title: '産前産後休業の申請', description: '勤怠システム > 休業申請', department: '人事部', deadline: '休業開始の1か月前まで' },
      { title: '育児休業申出書の提出', description: '人事システム > 各種届出 > 育児休業', department: '人事部', deadline: '開始予定日の1か月前まで' },
      { title: '慶弔金申請書（出産）の提出', description: '総務ポータル > 申請書ダウンロード', department: '総務部', deadline: '出産日から3か月以内' },
    ],
    inquiry: null,
  },
  {
    id: 'sidejob',
    match: /副業|兼業|ダブルワーク/,
    keyword: '副業',
    intent: '副業（兼業）が認められるか、どんな手続きが必要か知りたい',
    viewpoints: ['副業の可否', '許可の基準', '申請方法'],
    rounds: [
      {
        queries: ['副業', '兼業 許可', '競業避止'],
        hits: [['d1', 0.9, '第45条 兼業の許可'], ['d1', 0.66, '第46条 競業の禁止']],
        sufficient: false,
        evaluation: '「事前許可制」であることは分かりましたが、許可の判断基準と申請書の様式が見つかりません。追加検索します。',
      },
      {
        queries: ['兼業 申請書', '副業 ガイドライン', '兼業 判断基準'],
        hits: [],
        sufficient: false,
        evaluation: '閲覧可能な資料に該当情報がありませんでした。社内資料だけでは判断できないため、担当部署への問い合わせを提案します。',
      },
    ],
    answer: `社内規程では、副業（兼業）は **会社の事前許可制** となっています [1]。
また、会社と競合する事業や、業務に支障が出るおそれのある副業は認められません [2]。

ただし、**許可の判断基準や申請書の様式は、閲覧できる社内資料には記載がありませんでした。**
具体的な内容によって判断が変わるため、人事部へ確認することをおすすめします。`,
    sources: [
      ['d1', '第45条（兼業の許可）', 21, '従業員が他の会社の業務に従事し、又は自ら事業を営もうとするときは、あらかじめ会社の許可を得なければならない。'],
      ['d1', '第46条（競業の禁止）', 21, '従業員は、会社と競業する事業を営み、又は競業する他社の業務に従事してはならない。'],
    ],
    nextSteps: [],
    inquiry: {
      department: '人事部',
      reason: '許可の判断基準・申請書の様式が社内資料に見つかりませんでした',
      subject: '副業（兼業）の許可申請について',
      unclear: ['副業の許可の判断基準', '申請書の様式と提出先', '申請から許可までの期間'],
    },
  },
];

const FALLBACK = {
  id: 'fallback',
  intent: '社内の制度・手続きに関する情報を知りたい',
  viewpoints: ['関連する規程', '手続き方法', '担当部署'],
  rounds: [
    { queries: [], hits: [['d13', 0.41, '1章 総則'], ['d1', 0.36, '第1条 目的']], sufficient: false, evaluation: '関連度の高い資料が見つかりませんでした。検索語を言い換えて追加検索します。' },
    { queries: [], hits: [], sufficient: false, evaluation: '社内資料では回答に必要な情報を確認できませんでした。担当部署への問い合わせを提案します。' },
  ],
  answer: `ご質問の内容について社内資料を検索しましたが、**回答の根拠となる情報を見つけられませんでした。**

誤った案内を避けるため、AIによる推測での回答は控えます。担当部署へ問い合わせることをおすすめします。`,
  sources: [],
  nextSteps: [],
  inquiry: { department: '総務部', reason: '回答の根拠となる社内資料が見つかりませんでした', subject: null, unclear: ['ご質問の内容全般'] },
};

const docById = (id) => documents.find((d) => d.id === id);
let seq = 0;
const nextId = (prefix) => `${prefix}${Date.now().toString(36)}${(seq++).toString(36)}`;

function expandFallbackQueries(question) {
  const base = question.replace(/[？?。、！!]/g, ' ').trim().slice(0, 20);
  return [[base], [`${base} 手続き`, `${base} 規程`]];
}

function buildInquiryDraft(inquiry, question, user, sources) {
  const subject = inquiry.subject ?? `「${question.slice(0, 24)}」についての問い合わせ`;
  const sourceLines = sources.length ? sources.map((s) => `・${s.title} ${s.section}`).join('\n') : '・該当する資料は見つかりませんでした';
  const body = `${inquiry.department} ご担当者様

${user?.department ?? ''}の${user?.name?.split(' ')[0] ?? ''}です。
社内ナビAIで確認しましたが解決できなかったため、以下についてご確認をお願いいたします。

■ 質問内容
${question}

■ 確認済みの社内資料
${sourceLines}

■ 不明な点
${inquiry.unclear.map((u) => `・${u}`).join('\n')}

お手数ですが、よろしくお願いいたします。`;
  return { department: inquiry.department, reason: inquiry.reason, subject, body };
}

/**
 * 質問に対する Agent の処理結果を組み立てる。
 * @returns {{ steps: object[], message: object }}
 */
export function runAgent(question, user) {
  const scenario = SCENARIOS.find((s) => s.match.test(question)) ?? FALLBACK;
  const visibleCount = documents.filter((d) => d.status === 'indexed' && (d.visibility.type === 'all' || d.visibility.departments.includes(user?.department))).length;
  const fallbackQueries = scenario === FALLBACK ? expandFallbackQueries(question) : null;

  const steps = [];
  steps.push({ id: nextId('s'), type: 'analyze', title: '質問内容を分析', detail: `意図：${scenario.intent}`, items: scenario.viewpoints });
  steps.push({
    id: nextId('s'),
    type: 'plan',
    title: '検索戦略を決定',
    detail: scenario.keyword
      ? `「${scenario.keyword}」という語だけでなく、${scenario.viewpoints.length}つの観点に言い換えて検索します（閲覧可能な資料 ${visibleCount} 件が対象）`
      : `質問文から検索語を抽出して検索します（閲覧可能な資料 ${visibleCount} 件が対象）`,
    queries: fallbackQueries ? fallbackQueries[0] : scenario.rounds[0].queries,
  });

  scenario.rounds.forEach((round, i) => {
    steps.push({
      id: nextId('s'),
      type: 'search',
      title: i === 0 ? '社内資料を検索（1回目）' : `追加検索（${i + 1}回目）`,
      // 1回目の検索語は「検索戦略」ステップで表示済みのため、追加検索のときだけ載せる
      queries: i === 0 ? undefined : fallbackQueries ? fallbackQueries[i] : round.queries,
      results: round.hits.map(([docId, score, section]) => ({ documentId: docId, title: docById(docId).title, section, score })),
    });
    steps.push({
      id: nextId('s'),
      type: 'evaluate',
      title: round.sufficient ? '情報の充足度を評価：十分' : '情報の充足度を評価：不足あり',
      detail: round.evaluation,
      sufficient: round.sufficient,
    });
  });

  const sources = scenario.sources.map(([docId, section, page, excerpt], i) => {
    const doc = docById(docId);
    return { index: i + 1, documentId: docId, title: doc.title, fileType: doc.fileType, department: doc.department, updatedAt: doc.updatedAt, section, page, excerpt };
  });

  steps.push({
    id: nextId('s'),
    type: 'generate',
    title: '回答を作成',
    detail: sources.length ? `根拠資料 ${sources.length} 件をもとに回答を作成しました` : '根拠となる資料がないため、推測での回答は行いません',
  });

  const searchCount = scenario.rounds.length;
  const message = {
    id: nextId('m'),
    role: 'assistant',
    content: scenario.answer,
    createdAt: new Date().toISOString(),
    agent: { steps, searchCount, durationMs: 2400 + searchCount * 1300 },
    sources,
    nextSteps: scenario.nextSteps.map((s) => ({ ...s, id: nextId('t') })),
    inquirySuggestion: scenario.inquiry ? buildInquiryDraft(scenario.inquiry, question, user, sources) : null,
    feedback: null,
  };
  return { steps, message, scenarioId: scenario.id };
}

