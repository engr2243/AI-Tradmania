import { fmt } from '../utils/format';

function ExchangeRow({ name, ticker, ob }) {
  const price = ticker?.last;
  const change = ticker?.change_pct;
  const buyPressure = ob?.buy_pressure_pct ?? 50;
  const spread = ob?.spread;

  return (
    <div className="flex items-center gap-3 py-2 border-b border-slate-800/50 last:border-0">
      <div className="w-16 shrink-0">
        <span className="text-xs font-medium text-slate-300 capitalize">{name}</span>
      </div>
      <div className="flex-1">
        <p className="text-sm font-mono text-slate-200">{fmt.price(price)}</p>
      </div>
      <div className="w-14 text-right">
        <p className={`text-xs font-mono ${change >= 0 ? 'text-green-400' : 'text-red-400'}`}>
          {fmt.pct(change)}
        </p>
      </div>
      <div className="w-20">
        <div className="flex items-center gap-1">
          <div className="flex-1 h-1.5 bg-red-500/40 rounded-full overflow-hidden">
            <div className="h-full bg-green-500 rounded-full" style={{ width: `${buyPressure}%` }} />
          </div>
        </div>
        <p className="text-xs text-slate-500 mt-0.5">{buyPressure.toFixed(0)}% buy</p>
      </div>
      <div className="w-16 text-right shrink-0">
        <p className="text-xs text-slate-500">
          {spread != null ? `$${Number(spread).toFixed(1)} sprd` : '--'}
        </p>
      </div>
    </div>
  );
}

export default function MarketComparison({ tickers, orderBooks, symbol }) {
  const exchanges = Object.keys(tickers || {});

  // Compute price spread across exchanges
  const prices = exchanges.map(e => tickers[e]?.last).filter(Boolean);
  const minPrice = prices.length ? Math.min(...prices) : null;
  const maxPrice = prices.length ? Math.max(...prices) : null;
  const spreadPct = minPrice && maxPrice ? ((maxPrice - minPrice) / minPrice * 100).toFixed(3) : null;

  return (
    <div className="bg-slate-900 rounded-xl border border-slate-800 p-4">
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-slate-200 font-semibold text-sm tracking-wide">
          Market Comparison — {symbol || 'BTC/USDT'}
        </h2>
        {spreadPct && (
          <span className={`text-xs px-2 py-0.5 rounded ${parseFloat(spreadPct) > 0.1 ? 'bg-yellow-500/20 text-yellow-400' : 'bg-slate-800 text-slate-400'}`}>
            Cross-exchange spread: {spreadPct}%
          </span>
        )}
      </div>

      <div className="flex items-center gap-3 pb-1 border-b border-slate-700 text-xs text-slate-500 mb-1">
        <span className="w-16">Exchange</span>
        <span className="flex-1">Price</span>
        <span className="w-14 text-right">24h Chg</span>
        <span className="w-20">Buy Pressure</span>
        <span className="w-16 text-right">Spread</span>
      </div>

      {exchanges.length === 0 ? (
        <div className="py-4 text-center text-slate-600 text-xs">Connecting to exchanges...</div>
      ) : (
        exchanges.map(ex => (
          <ExchangeRow
            key={ex}
            name={ex}
            ticker={tickers[ex]}
            ob={orderBooks?.[ex]}
          />
        ))
      )}
    </div>
  );
}
