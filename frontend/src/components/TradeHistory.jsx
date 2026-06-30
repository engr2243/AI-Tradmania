import { fmt } from '../utils/format';

export default function TradeHistory({ trades = [] }) {
  const sorted = [...trades].reverse();

  return (
    <div className="bg-slate-900 rounded-xl border border-slate-800 p-4">
      <h2 className="text-slate-200 font-semibold text-sm tracking-wide mb-3">Trade History</h2>
      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="text-slate-500 border-b border-slate-800">
              <th className="text-left pb-2 font-normal">#</th>
              <th className="text-left pb-2 font-normal">Side</th>
              <th className="text-right pb-2 font-normal">Price</th>
              <th className="text-right pb-2 font-normal">Amount</th>
              <th className="text-right pb-2 font-normal">Cost</th>
              <th className="text-right pb-2 font-normal">P&L</th>
              <th className="text-right pb-2 font-normal">Time</th>
            </tr>
          </thead>
          <tbody>
            {sorted.length === 0 ? (
              <tr>
                <td colSpan={7} className="py-6 text-center text-slate-600">No trades yet</td>
              </tr>
            ) : (
              sorted.map(t => (
                <tr key={t.id} className="border-b border-slate-800/50 hover:bg-slate-800/30 transition-colors">
                  <td className="py-1.5 text-slate-600">{t.id}</td>
                  <td className="py-1.5">
                    <span className={`px-1.5 py-0.5 rounded font-semibold ${t.side === 'buy' ? 'text-green-400 bg-green-500/10' : 'text-red-400 bg-red-500/10'}`}>
                      {t.side.toUpperCase()}
                    </span>
                  </td>
                  <td className="py-1.5 text-right font-mono text-slate-200">{fmt.price(t.price)}</td>
                  <td className="py-1.5 text-right font-mono text-slate-300">{fmt.qty(t.amount, 5)}</td>
                  <td className="py-1.5 text-right font-mono text-slate-400">{fmt.price(t.cost)}</td>
                  <td className={`py-1.5 text-right font-mono ${t.pnl > 0 ? 'text-green-400' : t.pnl < 0 ? 'text-red-400' : 'text-slate-500'}`}>
                    {t.pnl !== 0 ? fmt.pnl(t.pnl) : '--'}
                  </td>
                  <td className="py-1.5 text-right text-slate-500">{fmt.ts(t.timestamp)}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
