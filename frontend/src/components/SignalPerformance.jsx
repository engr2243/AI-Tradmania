export default function SignalPerformance({ signals = [], riskStatus }) {
  return (
    <div className="bg-slate-900 rounded-xl border border-slate-800 p-4">
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-slate-200 font-semibold text-sm tracking-wide">Signal Performance</h2>
        {riskStatus && (
          <div className="flex items-center gap-2">
            <span className="text-xs text-slate-500">Scale:</span>
            <span className={`text-xs font-bold ${riskStatus.position_scale < 1 ? 'text-yellow-400' : 'text-green-400'}`}>
              {((riskStatus.position_scale || 1) * 100).toFixed(0)}%
            </span>
            {riskStatus.consecutive_losses > 0 && (
              <span className="text-xs text-red-400 bg-red-500/10 px-1.5 py-0.5 rounded">
                {riskStatus.consecutive_losses} loss streak
              </span>
            )}
          </div>
        )}
      </div>

      {signals.length === 0 ? (
        <p className="text-slate-600 text-xs py-2">
          Signal win rates appear here after trades close. Keep running.
        </p>
      ) : (
        <div className="space-y-2">
          {signals.map(s => (
            <div key={s.signal} className="flex items-center gap-2">
              <span className="text-slate-400 text-xs w-36 truncate">{s.signal}</span>
              <div className="flex-1 h-2 bg-slate-800 rounded-full overflow-hidden">
                <div
                  className="h-full rounded-full transition-all duration-700"
                  style={{
                    width: `${s.win_rate}%`,
                    backgroundColor: s.win_rate >= 60 ? '#22c55e' : s.win_rate >= 45 ? '#f59e0b' : '#ef4444',
                  }}
                />
              </div>
              <span className="text-xs font-mono text-slate-300 w-10 text-right">{s.win_rate}%</span>
              <span className="text-xs text-slate-600 w-12 text-right">{s.total} trades</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
