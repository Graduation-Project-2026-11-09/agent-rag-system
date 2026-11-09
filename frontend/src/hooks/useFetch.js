import { useCallback, useEffect, useState } from 'react';

/** API を呼び出して結果を保持する。deps が変わると再取得する。 */
export function useFetch(fn, deps = []) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const load = useCallback(() => {
    setLoading(true);
    setError(null);
    return fn()
      .then(setData)
      .catch(setError)
      .finally(() => setLoading(false));
    // 呼び出し側が渡す deps で再取得のタイミングを決めるため、配列リテラルにしない
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  useEffect(() => {
    load();
  }, [load]);

  return { data, setData, loading, error, reload: load };
}
