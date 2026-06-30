import { useWebSocket } from './hooks/useWebSocket';
import { fmt } from './utils/format';
import PriceChart from './components/PriceChart';
import AIDecisions from './components/AIDecisions';
import Portfolio from './components/Portfolio';
import MarketComparison from './components/MarketComparison';
import TradeHistory from './components/TradeHistory';
import Indicators from './components/Indicators';
import BotControls from './components/BotControls';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';
const WS_URL = API_BASE.replace('http', 'ws') + '/ws';

async function apiControl(body) {
  const res = await fetch(`${API_BASE}/api/control`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  return res.json();
}

export default function App() {
  const { state, connected, lastUpdate } = useWebSocket(WS_URL);

  const price = state?.current_price;
  const symbol = state?.symbol || 'BTC/USDT';
  const running = state?.running ?? false;
  const mode = state?.mode || 'paper';

  return (
    <div className="min-h-screen bg-slate-950 text-slate-200">
      {/* Header */}
      <header className="border-b border-slate-800 px-4 py-3 flex items-center justify-between sticky top-0 bg-slate-950/95 backdrop-blur z-10">
        <div className="flex items-center gap-3">
          <div className="w-7 h-7 bg-gradient-to-br from-blue-500 to-purple-600 rounded-lg flex items-center justify-center">
            <span className="text-white text-xs font-bold">AT</span>
          </div>
          <div>
            <h1 className="text-slate-100 font-bold text-base leading-none">AI-Tradmania</h1>
            <p className="text-slate-500 text-xs">Claude-powered crypto trading</p>
          </div>
        </div>

        <div className="flex items-center gap-4">
          {price && (
            <div className="text-right">
              <p className="text-slate-200 font-mono font-bold">{fmt.price(price)}</p>
              <p className="text-slate-500 text-xs">{symbol}</p>
            </div>
          )}

          <div className="flex items-center gap-2">
            <div className={`w-2 h-2 rounded-full ${connected ? 'bg-green-500 animate-pulse' : 'bg-red-500'}`} />
            <span className="text-xs text-slate-500">{connected ? 'Live' : 'Reconnecting...'}</span>
          </div>

          {lastUpdate && (
            <span className="text-xs text-slate-600 hidden sm:block">
              {fmt.ago(lastUpdate)}
            </span>
          )}
        </div>
      </header>

      <main className="max-w-screen-2xl mx-auto px-3 py-4 space-y-4">
        {/* Top: Portfolio */}
        <Portfolio
          portfolio={state?.portfolio}
          symbol={symbol}
          mode={mode}
        />

        {/* Middle: Chart + AI Decisions */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          <div className="lg:col-span-2">
            <PriceChart
              ohlcv={state?.ohlcv}
              trades={state?.recent_trades}
              symbol={symbol}
            />
          </div>
          <div className="min-h-[320px]">
            <AIDecisions
              decision={state?.decision}
              lastUpdate={lastUpdate}
              cycle={state?.cycle}
            />
          </div>
        </div>

        {/* Middle: Indicators + Controls + Market Comparison */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <Indicators indicators={state?.indicators} />
          <div>
            <BotControls
              running={running}
              mode={mode}
              symbol={symbol}
              riskHalted={state?.risk_halted}
              haltReason={state?.halt_reason}
              onControl={apiControl}
            />
          </div>
          <MarketComparison
            tickers={state?.tickers || {}}
            orderBooks={state?.order_books || {}}
            symbol={symbol}
          />
        </div>

        {/* Bottom: Trade History */}
        <TradeHistory trades={state?.recent_trades || []} />

        {/* Footer */}
        <footer className="text-center text-xs text-slate-700 pb-4">
          AI-Tradmania • Paper trading by default • Not financial advice
        </footer>
      </main>
    </div>
  );
}
