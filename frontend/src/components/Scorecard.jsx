function ScoreBar({ label, score, maxScore = 3 }) {
  const pct = ((score + maxScore) / (maxScore * 2)) * 100;
  const color = score > 0 ? '#22c55e' : score < 0 ? '#ef4444' : '#64748b';
  const bars = Math.abs(score);
  const isPos = score > 0;

  return (
    <div className="flex items-center gap-2 py-0.5">
      <span className="text-slate-500 text-xs w-36 shrink-0">{label}</span>
      <div className="flex items-center gap-0.5">
        {Array.from({ length: maxScore }).map((_, i) => (
          <div
            key={i}
            className="w-3 h-3 rounded-sm transition-all"
            style={{
              backgroundColor: isPos && i < bars ? '#22c55e' : !isPos && i < bars ? '#ef4444' : '#1e293b',
              transform: isPos ? 'none' : 'scaleX(-1)',
            }}
          />
        ))}
      </div>
      <span className="text-xs font-mono font-semibold w-6 text-right" style={{ color }}>
        {score > 0 ? `+${score}` : score}
      </span>
    </div>
  );
}

function MtfRow({ tf, data }) {
  if (!data) return null;
  const biasColor = data.bias === 'bullish' ? 'text-green-400' : data.bias === 'bearish' ? 'text-red-400' : 'text-yellow-400';
  return (
    <div className="flex items-center gap-2 py-1 border-b border-slate-800/40 last:border-0 text-xs">
      <span className="text-slate-500 w-6 font-mono">{tf}</span>
      <span className={`font-bold w-14 ${biasColor}`}>{(data.bias || 'neutral').toUpperCase()}</span>
      <span className="text-slate-500">EMA:{data.ema_trend?.slice(0,4)}</span>
      <span className="text-slate-500">MACD:{data.macd_trend?.slice(0,4)}</span>
      <span className="text-slate-500">RSI:{data.rsi ?? 'N/A'}</span>
      <span className="text-slate-600 ml-auto">{data.regime?.replace('_', ' ')}</span>
    </div>
  );
}

export default function Scorecard({ scorecard, mtf, fearGreed, fundingRate }) {
  if (!scorecard) return null;

  const scores = scorecard.scores || {};
  const total = scorecard.total || 0;
  const bias = scorecard.overall_bias || 'neutral';
  const alignment = mtf?.alignment || {};
  const perTf = alignment.per_tf || {};
  const confluence = alignment.confluence || 'unknown';

  const biasColor = bias === 'bullish' ? 'text-green-400' : bias === 'bearish' ? 'text-red-400' : 'text-yellow-400';
  const confluenceColor = confluence.includes('strong') ? (confluence.includes('bullish') ? 'text-green-400' : 'text-red-400') : 'text-yellow-400';

  return (
    <div className="bg-slate-900 rounded-xl border border-slate-800 p-4">
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-slate-200 font-semibold text-sm tracking-wide">Signal Scorecard</h2>
        <div className="flex items-center gap-2">
          <span className={`text-sm font-bold font-mono ${biasColor}`}>
            {total > 0 ? `+${total}` : total} / {scorecard.max_possible}
          </span>
          <span className={`text-xs px-2 py-0.5 rounded font-semibold ${biasColor} bg-slate-800`}>
            {bias.toUpperCase()}
          </span>
        </div>
      </div>

      <div className="space-y-0.5 mb-4">
        <ScoreBar label="Trend (EMA/Cross)" score={scores.trend ?? 0} maxScore={3} />
        <ScoreBar label="Momentum (MACD/RSI)" score={scores.momentum ?? 0} maxScore={3} />
        <ScoreBar label="Volume" score={scores.volume ?? 0} maxScore={2} />
        <ScoreBar label="MTF Confluence" score={scores.mtf_confluence ?? 0} maxScore={3} />
        <ScoreBar label="Sentiment (F&G)" score={scores.sentiment ?? 0} maxScore={2} />
        <ScoreBar label="Funding Rate" score={scores.funding_rate ?? 0} maxScore={2} />
        <ScoreBar label="BB Position" score={scores.bb_position ?? 0} maxScore={2} />
      </div>

      {/* Multi-timeframe */}
      <div className="border-t border-slate-800 pt-3 mb-3">
        <div className="flex items-center justify-between mb-2">
          <p className="text-slate-500 text-xs">Multi-Timeframe</p>
          <span className={`text-xs font-semibold ${confluenceColor}`}>
            {confluence.replace(/_/g, ' ').toUpperCase()}
          </span>
        </div>
        {['5m', '1h', '4h'].map(tf => (
          <MtfRow key={tf} tf={tf} data={perTf[tf]} />
        ))}
      </div>

      {/* External signals */}
      <div className="grid grid-cols-2 gap-2">
        {fearGreed && (
          <div className="bg-slate-800/60 rounded-lg px-3 py-2">
            <p className="text-slate-500 text-xs mb-0.5">Fear & Greed</p>
            <p className={`text-sm font-bold ${fearGreed.score <= 35 ? 'text-green-400' : fearGreed.score >= 65 ? 'text-red-400' : 'text-yellow-400'}`}>
              {fearGreed.score} — {fearGreed.label}
            </p>
            <p className="text-slate-600 text-xs">{fearGreed.trend}</p>
          </div>
        )}
        {fundingRate && (
          <div className="bg-slate-800/60 rounded-lg px-3 py-2">
            <p className="text-slate-500 text-xs mb-0.5">Funding Rate</p>
            <p className={`text-sm font-bold font-mono ${fundingRate.rate_pct > 0.05 ? 'text-red-400' : fundingRate.rate_pct < -0.03 ? 'text-green-400' : 'text-slate-300'}`}>
              {fundingRate.rate_pct > 0 ? '+' : ''}{fundingRate.rate_pct?.toFixed(4)}%
            </p>
            <p className="text-slate-600 text-xs">per 8h</p>
          </div>
        )}
      </div>
    </div>
  );
}
