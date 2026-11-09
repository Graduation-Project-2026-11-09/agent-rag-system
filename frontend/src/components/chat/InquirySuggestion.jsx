import { MessageSquareShare, CheckCircle2 } from 'lucide-react';

/** Agent が「社内資料だけでは解決できない」と判断したときだけ表示する */
export default function InquirySuggestion({ suggestion, inquiryId, dismissed, onCreate, onDismiss }) {
  if (inquiryId) {
    return (
      <div className="inquiry-suggest sent">
        <CheckCircle2 size={16} /> 担当部署へ問い合わせ済みです。回答は「問い合わせ履歴」で確認できます。
      </div>
    );
  }
  if (dismissed) return null;
  return (
    <div className="inquiry-suggest">
      <div className="inquiry-suggest-text">
        <MessageSquareShare size={18} />
        <div>
          <p><strong>{suggestion.department}</strong>への問い合わせを作成しますか？</p>
          <p className="muted small">理由：{suggestion.reason}。これまでの質問内容と確認済みの資料をもとに下書きを作成します。</p>
        </div>
      </div>
      <div className="row gap-sm">
        <button className="btn btn-sm" onClick={onDismiss}>今回は不要</button>
        <button className="btn btn-sm btn-primary" onClick={onCreate}>問い合わせ文を作成</button>
      </div>
    </div>
  );
}
