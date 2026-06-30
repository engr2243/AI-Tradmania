import { fmt } from '../utils/format';

function Stat({ label, value, sub, highlight }) {
  return (
    <div className="bg-slate-800/60 rounded-lg px-3 py-2.5">
      <p className="text-slate-500 text-xs mb-0.5">{label}</p>
      <p className={`font-mono font-semibold text-sm ${highlight || 'text-slate-200'}`}>{value}</p>
      {sub && <p className="text-slate-600 text-xs mt-0.5">{sub}</p>}
    </div>
  );
}

export default function Portfolio({ portfolio, symbol, mode }) {
  if (!portfolio) return null;

  const {
    balance_usdt,
    holdings,
    holdings_value,
    total_value,
    avg_buy_price,
    unrealized_pnl,
    realized_pnl,
    total_pnl,
    total_pnl_pct,
    daily_drawdown_pct,
    trade_count,
  } = portfolio;

  const pnlColor = total_pnl >= 0 ? 'text-green-400' : 'text-red-400';
  const drawdownColor = daily_drawdown_pct > 7 ? 'text-red-400' : daily_drawdown_pct > 3 ? 'text-yellow-400' : 'text-green-400';
  const base = symbol?.split('/')[0] || 'BTC';

  return (
    <div className="bg-slate-900 rounded-xl border border-slate-800 p-4">
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-slate-200 font-semibold text-sm tracking-wide">Portfolio</h2>
        <span className={`text-xs px-2 py-0.5 rounded font-medium ${mode === 'live' ? 'bg-green-500/20 text-green-400' : 'bg-yellow-500/20 text-yellow-400'}`}>
          {mode === 'live' ? 'LIVE' : 'PAPER'}
        </span>
      </div>

      <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
        <Stat label="Total Value" value={fmt.price(total_value)} />
        <Stat
          label="Total P&L"
          value={fmt.pnl(total_pnl)}
          sub={fmt.pct(total_pnl_pct)}
          highlight={pnlColor}
        />
        <Stat label="USDT Balance" value={fmt.price(balance_usdt)} />
        <Stat
          label={`${base} Holdings`}
          value={fmt.qty(holdings)}
          sub={fmt.price(holdings_value)}
        />
      </div>

      <div className="grid grid-cols-2 gap-2 sm:grid-cols-4 mt-2">
        <Stat
          label="Unrealized P&L"
          value={fmt.pnl(unrealized_pnl)}
          highlight={unrealized_pnl >= 0 ? 'text-green-400' : 'text-red-400'}
        />
        <Stat
          label="Realized P&L"
          value={fmt.pnl(realized_pnl)}
          highlight={realized_pnl >= 0 ? 'text-green-400' : 'text-red-400'}
        />
        <Stat
          label="Avg Buy Price"
          value={avg_buy_price ? fmt.price(avg_buy_price) : '--'}
        />
        <div className="bg-slate-800/60 rounded-lg px-3 py-2.5">
          <p className="text-slate-500 text-xs mb-0.5">Daily Drawdown</p>
          <div className="flex items-center gap-2">
            <div className="flex-1 h-1.5 bg-slate-700 rounded-full overflow-hidden">
              <div
                className="h-full rounded-full transition-all duration-500 bg-red-500"
                style={{ width: `${Math.min(daily_drawdown_pct || 0, 100)}%` }}
              />
            </div>
            <span className={`text-xs font-mono font-semibold ${drawdownColor}`}>
              {(daily_drawdown_pct || 0).toFixed(1)}%
            </span>
          </div>
          <p className="text-slate-600 text-xs mt-0.5">{trade_count} trades</p>
        </div>
      </div>
    </div>
  );
}
