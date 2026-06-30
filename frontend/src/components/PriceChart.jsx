import { useEffect, useRef } from 'react';
import { createChart } from 'lightweight-charts';

export default function PriceChart({ ohlcv, trades = [], symbol }) {
  const containerRef = useRef(null);
  const chartRef = useRef(null);
  const candleRef = useRef(null);
  const markerDataRef = useRef([]);

  useEffect(() => {
    if (!containerRef.current) return;

    const chart = createChart(containerRef.current, {
      layout: { background: { color: '#0f172a' }, textColor: '#94a3b8' },
      grid: { vertLines: { color: '#1e293b' }, horzLines: { color: '#1e293b' } },
      crosshair: { mode: 1 },
      rightPriceScale: { borderColor: '#1e293b' },
      timeScale: { borderColor: '#1e293b', timeVisible: true },
      width: containerRef.current.clientWidth,
      height: 320,
    });

    const candleSeries = chart.addCandlestickSeries({
      upColor: '#22c55e',
      downColor: '#ef4444',
      borderUpColor: '#22c55e',
      borderDownColor: '#ef4444',
      wickUpColor: '#22c55e',
      wickDownColor: '#ef4444',
    });

    chartRef.current = chart;
    candleRef.current = candleSeries;

    const ro = new ResizeObserver(() => {
      if (containerRef.current) {
        chart.applyOptions({ width: containerRef.current.clientWidth });
      }
    });
    ro.observe(containerRef.current);

    return () => {
      ro.disconnect();
      chart.remove();
    };
  }, []);

  useEffect(() => {
    if (!candleRef.current || !ohlcv?.length) return;

    const data = ohlcv
      .map(([ts, open, high, low, close]) => ({
        time: Math.floor(ts / 1000),
        open: Number(open),
        high: Number(high),
        low: Number(low),
        close: Number(close),
      }))
      .sort((a, b) => a.time - b.time)
      .filter((d, i, arr) => i === 0 || d.time !== arr[i - 1].time);

    candleRef.current.setData(data);
  }, [ohlcv]);

  useEffect(() => {
    if (!candleRef.current || !trades?.length) return;

    const markers = trades
      .filter(t => t.price && t.timestamp)
      .map(t => ({
        time: Math.floor(t.timestamp / 1000),
        position: t.side === 'buy' ? 'belowBar' : 'aboveBar',
        color: t.side === 'buy' ? '#22c55e' : '#ef4444',
        shape: t.side === 'buy' ? 'arrowUp' : 'arrowDown',
        text: `${t.side.toUpperCase()} $${Number(t.price).toFixed(0)}`,
      }));

    markerDataRef.current = markers;
    try {
      candleRef.current.setMarkers(markers.sort((a, b) => a.time - b.time));
    } catch {
      // marker API may not be available in all versions
    }
  }, [trades]);

  return (
    <div className="bg-slate-900 rounded-xl p-4 border border-slate-800">
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-slate-200 font-semibold text-sm tracking-wide">
          {symbol || 'BTC/USDT'} — Price Chart (5m)
        </h2>
        <div className="flex gap-3 text-xs text-slate-500">
          <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-green-500 inline-block" /> Buy</span>
          <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-red-500 inline-block" /> Sell</span>
        </div>
      </div>
      <div ref={containerRef} className="w-full" />
    </div>
  );
}
