import { useEffect, useState } from 'react'

// 環境構築の確認用画面。モックアップの画面に置き換えていく
export default function App() {
  const [health, setHealth] = useState(null)

  useEffect(() => {
    fetch('/api/health')
      .then((res) => res.json())
      .then(setHealth)
      .catch(() => setHealth({ status: 'error' }))
  }, [])

  return (
    <main style={{ fontFamily: 'sans-serif', padding: 24 }}>
      <h1>社内問い合わせ・業務支援システム</h1>
      <p>API: {health ? `${health.status}（DB: ${health.db ? 'OK' : 'NG'}）` : '確認中…'}</p>
    </main>
  )
}
