import { useState } from 'react';

const SYMBOLS = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'BNB/USDT', 'XRP/USDT'];

const PROVIDERS = [
  { value: 'claude',   label: 'Claude',   sub: 'claude-sonnet-4-6',  color: 'text-purple-400' },
  { value: 'openai',   label: 'OpenAI',   sub: 'gpt-4o',             color: 'text-green-400'  },
  { value: 'moonshot', label: 'Moonshot', sub: 'moonshot-v1-8k',     color: 'text-blue-400'   },
  { value: 'deepseek', label: 'DeepSeek', sub: 'deepseek-chat',      color: 'text-cyan-400'   },
];

export default function BotControls({ running, mode, symbol, aiProvider, riskHalted, haltReason, onControl }) {
  const [selectedSymbol, setSelectedSymbol] = useState(symbol || 'BTC/USDT');
  const [selectedMode, setSelectedMode] = useState(mode || 'paper');
  const [selectedProvider, setSelectedProvider] = useState(aiProvider || 'claude');
  const [loading, setLoading] = useState(false);
  const [switchingProvider, setSwitchingProvider] = useState(false);
  const [providerError, setProviderError] = useState('');

  const send = async (action, extra = {}) => {
    setLoading(true);
    try {
      await onControl({ action, symbol: selectedSymbol, mode: selectedMode, ...extra });
    } finally {
      setLoading(false);
    }
  };

  const handleProviderChange = async (value) => {
    setSelectedProvider(value);
    setProviderError('');
    setSwitchingProvider(true);
    try {
      const res = await onControl({ action: 'set_provider', provider: value });
      if (res?.error) setProviderError(res.error);
    } catch (e) {
      setProviderError('Failed to switch provider — check API key in .env');
    } finally {
      setSwitchingProvider(false);
    }
  };

  const activeProviderInfo = PROVIDERS.find(p => p.value === (aiProvider || selectedProvider));

  return (
    <div className="bg-slate-900 rounded-xl border border-slate-800 p-4">
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-slate-200 font-semibold text-sm tracking-wide">Bot Controls</h2>
        <div className="flex items-center gap-2">
          <div className={`w-2 h-2 rounded-full ${running ? 'bg-green-500 animate-pulse' : 'bg-slate-600'}`} />
          <span className={`text-xs ${running ? 'text-green-400' : 'text-slate-500'}`}>
            {running ? 'Running' : 'Stopped'}
          </span>
        </div>
      </div>

      {riskHalted && (
        <div className="mb-3 bg-red-500/10 border border-red-500/30 rounded-lg px-3 py-2">
          <p className="text-red-400 text-xs font-semibold">Risk Halt Active</p>
          <p className="text-red-300 text-xs mt-0.5">{haltReason}</p>
          <button
            onClick={() => send('resume')}
            className="mt-2 text-xs text-red-400 hover:text-red-300 underline"
          >
            Clear halt and resume
          </button>
        </div>
      )}

      {/* AI Provider selector */}
      <div className="mb-3">
        <label className="text-slate-500 text-xs block mb-1">AI Provider</label>
        <div className="grid grid-cols-2 gap-1.5">
          {PROVIDERS.map(p => (
            <button
              key={p.value}
              onClick={() => handleProviderChange(p.value)}
              disabled={switchingProvider}
              className={`flex flex-col items-start px-2.5 py-1.5 rounded-lg border text-xs transition-all ${
                (aiProvider || selectedProvider) === p.value
                  ? 'border-blue-500/50 bg-blue-500/10'
                  : 'border-slate-700 bg-slate-800/50 hover:border-slate-600'
              } disabled:opacity-50`}
            >
              <span className={`font-semibold ${(aiProvider || selectedProvider) === p.value ? p.color : 'text-slate-400'}`}>
                {p.label}
              </span>
              <span className="text-slate-600 font-mono" style={{ fontSize: '10px' }}>{p.sub}</span>
            </button>
          ))}
        </div>
        {switchingProvider && (
          <p className="text-xs text-slate-500 mt-1">Switching provider...</p>
        )}
        {providerError && (
          <p className="text-xs text-red-400 mt-1">{providerError}</p>
        )}
        {activeProviderInfo && !providerError && (
          <p className="text-xs text-slate-600 mt-1">
            Using <span className={activeProviderInfo.color}>{activeProviderInfo.label}</span>
            {' · '}{activeProviderInfo.sub}
          </p>
        )}
      </div>

      <div className="grid grid-cols-2 gap-3 mb-3">
        <div>
          <label className="text-slate-500 text-xs block mb-1">Symbol</label>
          <select
            value={selectedSymbol}
            onChange={e => setSelectedSymbol(e.target.value)}
            className="w-full bg-slate-800 text-slate-200 text-sm rounded-lg px-3 py-2 border border-slate-700 focus:outline-none focus:border-blue-500"
            disabled={running}
          >
            {SYMBOLS.map(s => <option key={s} value={s}>{s}</option>)}
          </select>
        </div>
        <div>
          <label className="text-slate-500 text-xs block mb-1">Mode</label>
          <select
            value={selectedMode}
            onChange={e => setSelectedMode(e.target.value)}
            className="w-full bg-slate-800 text-slate-200 text-sm rounded-lg px-3 py-2 border border-slate-700 focus:outline-none focus:border-blue-500"
            disabled={running}
          >
            <option value="paper">Paper Trading</option>
            <option value="live">Live Trading</option>
          </select>
        </div>
      </div>

      <div className="flex gap-2">
        {!running ? (
          <button
            onClick={() => send('start')}
            disabled={loading}
            className="flex-1 bg-green-600 hover:bg-green-500 disabled:opacity-50 text-white text-sm font-semibold py-2 rounded-lg transition-colors"
          >
            {loading ? 'Starting...' : 'Start Bot'}
          </button>
        ) : (
          <button
            onClick={() => send('stop')}
            disabled={loading}
            className="flex-1 bg-red-600 hover:bg-red-500 disabled:opacity-50 text-white text-sm font-semibold py-2 rounded-lg transition-colors"
          >
            {loading ? 'Stopping...' : 'Stop Bot'}
          </button>
        )}
      </div>

      <div className="mt-2 text-xs text-slate-600 text-center">
        {selectedMode === 'live' && (
          <span className="text-yellow-500">Live mode requires exchange API keys in .env</span>
        )}
        {selectedMode === 'paper' && 'Paper trading — no real funds at risk'}
      </div>
    </div>
  );
}
