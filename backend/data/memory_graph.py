"""
Neo4j long-term memory layer for AI-Tradmania.

Graph schema:
  (:Decision {id, timestamp, action, confidence, amount_pct, price_at, reason, rr_ratio, mode})
  (:MarketCondition {regime, mtf_confluence, rsi_band, scorecard_total, scorecard_bias,
                     fear_greed_score, funding_rate_sign, volume_ratio_band, bb_zone, macd_trend})
  (:Signal {name})
  (:Outcome {pnl, pnl_pct, result, exit_price, hold_duration_s})
  (:Regime {name})           -- ranging | trending | strong_trend
  (:Confluence {name})       -- strong_bullish | mild_bullish | mixed | etc.
  (:TimeContext {hour_utc, day_of_week, session})

Relationships:
  (Decision)-[:MADE_IN]->(MarketCondition)
  (Decision)-[:TRIGGERED_BY]->(Signal)
  (Decision)-[:RESULTED_IN]->(Outcome)
  (Decision)-[:AT_TIME]->(TimeContext)
  (MarketCondition)-[:HAS_REGIME]->(Regime)
  (MarketCondition)-[:HAS_CONFLUENCE]->(Confluence)
  (Signal)-[:CO_OCCURS_WITH {count}]->(Signal)     -- updated on each save
"""

import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Optional

from neo4j import GraphDatabase
from neo4j.exceptions import ServiceUnavailable

from config import NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD

logger = logging.getLogger(__name__)


class MemoryGraph:
    def __init__(self):
        self._driver = None
        self.available = False

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def connect(self):
        try:
            self._driver = GraphDatabase.driver(
                NEO4J_URI,
                auth=(NEO4J_USER, NEO4J_PASSWORD),
            )
            self._driver.verify_connectivity()
            self._ensure_indexes()
            self.available = True
            logger.info(f"Neo4j connected: {NEO4J_URI}")
        except ServiceUnavailable as e:
            logger.warning(f"Neo4j unavailable — memory layer disabled: {e}")
            self.available = False
        except Exception as e:
            logger.warning(f"Neo4j connection failed: {e}")
            self.available = False

    def close(self):
        if self._driver:
            self._driver.close()

    def _ensure_indexes(self):
        with self._driver.session() as s:
            s.run("CREATE INDEX decision_id IF NOT EXISTS FOR (d:Decision) ON (d.id)")
            s.run("CREATE INDEX decision_ts IF NOT EXISTS FOR (d:Decision) ON (d.timestamp)")
            s.run("CREATE INDEX signal_name IF NOT EXISTS FOR (s:Signal) ON (s.name)")
            s.run("CREATE INDEX regime_name IF NOT EXISTS FOR (r:Regime) ON (r.name)")
            s.run("CREATE INDEX confluence_name IF NOT EXISTS FOR (c:Confluence) ON (c.name)")

    # ── Write: save a new decision ────────────────────────────────────────────

    def save_decision(
        self,
        decision: dict,
        indicators: dict,
        mtf_alignment: dict,
        fear_greed: Optional[dict],
        funding_rate: Optional[dict],
        scorecard: dict,
        current_price: float,
        mode: str = "paper",
    ) -> Optional[str]:
        if not self.available:
            return None

        decision_id = str(uuid.uuid4())
        now = int(time.time() * 1000)
        dt = datetime.now(timezone.utc)

        # Discretize continuous values into bands for graph matching
        rsi = indicators.get("rsi_14")
        rsi_band = _rsi_band(rsi)
        vol_ratio = indicators.get("volume_ratio", 1.0)
        vol_band = _volume_band(vol_ratio)
        bb_pct = indicators.get("bb_pct", 0.5)
        bb_zone = _bb_zone(bb_pct)
        fg_score = fear_greed.get("score") if fear_greed else None
        funding_sign = _funding_sign(funding_rate.get("rate", 0) if funding_rate else 0)
        regime = indicators.get("regime", "unknown")
        confluence = mtf_alignment.get("confluence", "unknown")
        macd_trend = indicators.get("macd_trend", "unknown")
        scorecard_total = scorecard.get("total", 0)
        scorecard_bias = scorecard.get("overall_bias", "neutral")
        key_signals = decision.get("key_signals", [])
        session_label = _session_label(dt.hour)

        cypher = """
        // Create Decision node
        CREATE (d:Decision {
            id: $decision_id,
            timestamp: $timestamp,
            action: $action,
            confidence: $confidence,
            amount_pct: $amount_pct,
            price_at: $price_at,
            reason: $reason,
            rr_ratio: $rr_ratio,
            mode: $mode,
            outcome: 'pending',
            pnl: null
        })

        // MarketCondition node (MERGE — reuse identical conditions)
        MERGE (mc:MarketCondition {
            regime: $regime,
            mtf_confluence: $confluence,
            rsi_band: $rsi_band,
            scorecard_bias: $scorecard_bias,
            macd_trend: $macd_trend,
            bb_zone: $bb_zone,
            vol_band: $vol_band,
            funding_sign: $funding_sign
        })
        ON CREATE SET mc.scorecard_total_avg = $scorecard_total,
                      mc.fear_greed_avg = $fg_score,
                      mc.seen_count = 1
        ON MATCH  SET mc.scorecard_total_avg = (mc.scorecard_total_avg + $scorecard_total) / 2,
                      mc.seen_count = mc.seen_count + 1

        // Regime + Confluence nodes
        MERGE (r:Regime {name: $regime})
        MERGE (c:Confluence {name: $confluence})
        MERGE (mc)-[:HAS_REGIME]->(r)
        MERGE (mc)-[:HAS_CONFLUENCE]->(c)

        // TimeContext node
        MERGE (tc:TimeContext {hour_utc: $hour_utc, day_of_week: $day_of_week})
        ON CREATE SET tc.session = $session

        // Wire Decision
        CREATE (d)-[:MADE_IN]->(mc)
        CREATE (d)-[:AT_TIME]->(tc)

        RETURN d.id AS id
        """

        params = {
            "decision_id": decision_id,
            "timestamp": now,
            "action": decision.get("action"),
            "confidence": decision.get("confidence", 0),
            "amount_pct": decision.get("amount_pct", 0),
            "price_at": round(current_price, 2),
            "reason": decision.get("reason", ""),
            "rr_ratio": decision.get("rr_ratio"),
            "mode": mode,
            "regime": regime,
            "confluence": confluence,
            "rsi_band": rsi_band,
            "scorecard_total": scorecard_total,
            "scorecard_bias": scorecard_bias,
            "macd_trend": macd_trend,
            "bb_zone": bb_zone,
            "vol_band": vol_band,
            "funding_sign": funding_sign,
            "fg_score": float(fg_score) if fg_score is not None else 50.0,
            "hour_utc": dt.hour,
            "day_of_week": dt.weekday(),
            "session": session_label,
        }

        try:
            with self._driver.session() as s:
                result = s.run(cypher, params)
                record = result.single()

            # Create Signal nodes and TRIGGERED_BY edges
            if key_signals:
                self._save_signals(decision_id, key_signals)

            logger.debug(f"Memory saved: {decision_id} ({decision.get('action')})")
            return decision_id
        except Exception as e:
            logger.error(f"Neo4j save_decision error: {e}")
            return None

    def _save_signals(self, decision_id: str, signals: list[str]):
        """Create Signal nodes, TRIGGERED_BY edges, and CO_OCCURS_WITH edges."""
        cypher_signals = """
        MATCH (d:Decision {id: $decision_id})
        WITH d
        UNWIND $signals AS sig_name
        MERGE (s:Signal {name: sig_name})
        ON CREATE SET s.total_uses = 1, s.wins = 0, s.losses = 0
        ON MATCH  SET s.total_uses = s.total_uses + 1
        MERGE (d)-[:TRIGGERED_BY]->(s)
        """
        # Co-occurrence edges between every pair of signals
        cypher_cooccur = """
        UNWIND $pairs AS pair
        MERGE (s1:Signal {name: pair[0]})
        MERGE (s2:Signal {name: pair[1]})
        MERGE (s1)-[r:CO_OCCURS_WITH]->(s2)
        ON CREATE SET r.count = 1
        ON MATCH  SET r.count = r.count + 1
        """
        pairs = [
            [signals[i], signals[j]]
            for i in range(len(signals))
            for j in range(i + 1, len(signals))
        ]
        try:
            with self._driver.session() as s:
                s.run(cypher_signals, {"decision_id": decision_id, "signals": signals})
                if pairs:
                    s.run(cypher_cooccur, {"pairs": pairs})
        except Exception as e:
            logger.error(f"Signal save error: {e}")

    # ── Write: resolve outcome ────────────────────────────────────────────────

    def resolve_outcome(self, decision_id: str, pnl: float, exit_price: float, hold_duration_s: int = 0):
        if not self.available or not decision_id:
            return

        result_label = "profit" if pnl > 0 else "loss" if pnl < 0 else "breakeven"

        cypher = """
        MATCH (d:Decision {id: $decision_id})
        SET d.outcome = $result, d.pnl = $pnl

        // Create Outcome node
        CREATE (o:Outcome {
            pnl: $pnl,
            result: $result,
            exit_price: $exit_price,
            hold_duration_s: $hold_duration_s,
            timestamp: $ts
        })
        CREATE (d)-[:RESULTED_IN]->(o)

        // Update Signal win/loss counts
        WITH d
        MATCH (d)-[:TRIGGERED_BY]->(s:Signal)
        SET s.wins   = CASE WHEN $pnl > 0 THEN s.wins   + 1 ELSE s.wins   END,
            s.losses = CASE WHEN $pnl < 0 THEN s.losses + 1 ELSE s.losses END

        // Update MarketCondition aggregate P&L
        WITH d
        MATCH (d)-[:MADE_IN]->(mc:MarketCondition)
        SET mc.total_pnl    = COALESCE(mc.total_pnl, 0) + $pnl,
            mc.total_trades = COALESCE(mc.total_trades, 0) + 1,
            mc.wins         = CASE WHEN $pnl > 0 THEN COALESCE(mc.wins, 0) + 1 ELSE COALESCE(mc.wins, 0) END
        """
        try:
            with self._driver.session() as s:
                s.run(cypher, {
                    "decision_id": decision_id,
                    "pnl": round(pnl, 4),
                    "result": result_label,
                    "exit_price": round(exit_price, 2),
                    "hold_duration_s": hold_duration_s,
                    "ts": int(time.time() * 1000),
                })
            logger.debug(f"Outcome resolved: {decision_id} → {result_label} ${pnl:+.2f}")
        except Exception as e:
            logger.error(f"Neo4j resolve_outcome error: {e}")

    # ── Read: similar past situations ─────────────────────────────────────────

    def query_similar_situations(
        self,
        regime: str,
        confluence: str,
        rsi_band: str,
        scorecard_bias: str,
        action: str = "BUY",
        limit: int = 10,
    ) -> list[dict]:
        """
        Find past decisions made in similar market conditions.
        Returns decisions that have resolved outcomes.
        """
        if not self.available:
            return []

        cypher = """
        MATCH (d:Decision)-[:MADE_IN]->(mc:MarketCondition)
        WHERE mc.regime = $regime
          AND mc.scorecard_bias = $scorecard_bias
          AND d.action = $action
          AND d.outcome <> 'pending'
        OPTIONAL MATCH (d)-[:TRIGGERED_BY]->(s:Signal)
        OPTIONAL MATCH (d)-[:RESULTED_IN]->(o:Outcome)
        WITH d, mc, o, collect(s.name) AS signals
        ORDER BY d.timestamp DESC
        LIMIT $limit
        RETURN d.id AS id,
               d.action AS action,
               d.confidence AS confidence,
               d.price_at AS price_at,
               d.outcome AS outcome,
               d.pnl AS pnl,
               mc.regime AS regime,
               mc.mtf_confluence AS confluence,
               mc.rsi_band AS rsi_band,
               signals,
               o.hold_duration_s AS hold_s
        """
        try:
            with self._driver.session() as s:
                result = s.run(cypher, {
                    "regime": regime,
                    "scorecard_bias": scorecard_bias,
                    "action": action,
                    "limit": limit,
                })
                return [dict(r) for r in result]
        except Exception as e:
            logger.error(f"Neo4j similar_situations error: {e}")
            return []

    # ── Read: analytics for prompt injection ──────────────────────────────────

    def get_regime_performance(self) -> list[dict]:
        """Win rates and avg P&L per regime + action combination."""
        if not self.available:
            return []
        cypher = """
        MATCH (d:Decision)-[:MADE_IN]->(mc:MarketCondition)-[:HAS_REGIME]->(r:Regime)
        WHERE d.outcome <> 'pending'
        RETURN r.name AS regime,
               d.action AS action,
               count(*) AS total,
               sum(CASE WHEN d.pnl > 0 THEN 1 ELSE 0 END) AS wins,
               round(avg(d.pnl) * 100) / 100 AS avg_pnl,
               round(sum(d.pnl) * 100) / 100 AS total_pnl
        ORDER BY regime, action
        """
        try:
            with self._driver.session() as s:
                return [dict(r) for r in s.run(cypher)]
        except Exception as e:
            logger.error(f"Neo4j regime_performance error: {e}")
            return []

    def get_best_signal_combos(self, min_occurrences: int = 2) -> list[dict]:
        """Signal pairs with highest win rates (co-occurrence graph traversal)."""
        if not self.available:
            return []
        cypher = """
        MATCH (s1:Signal)-[co:CO_OCCURS_WITH]->(s2:Signal)
        WHERE co.count >= $min_occ AND s1.name < s2.name
        MATCH (d:Decision)-[:TRIGGERED_BY]->(s1)
        MATCH (d)-[:TRIGGERED_BY]->(s2)
        WHERE d.outcome <> 'pending'
        WITH s1.name AS sig1, s2.name AS sig2,
             count(d) AS total,
             sum(CASE WHEN d.pnl > 0 THEN 1 ELSE 0 END) AS wins,
             round(avg(d.pnl) * 100) / 100 AS avg_pnl
        WHERE total >= $min_occ
        RETURN sig1, sig2, total, wins,
               round(toFloat(wins) / total * 100) AS win_rate_pct,
               avg_pnl
        ORDER BY win_rate_pct DESC, total DESC
        LIMIT 8
        """
        try:
            with self._driver.session() as s:
                return [dict(r) for r in s.run(cypher, {"min_occ": min_occurrences})]
        except Exception as e:
            logger.error(f"Neo4j signal_combos error: {e}")
            return []

    def get_anti_patterns(self) -> list[dict]:
        """Signal + regime combinations that consistently lose."""
        if not self.available:
            return []
        cypher = """
        MATCH (d:Decision)-[:TRIGGERED_BY]->(s:Signal)
        MATCH (d)-[:MADE_IN]->(mc:MarketCondition)
        WHERE d.outcome = 'loss'
        WITH s.name AS signal, mc.regime AS regime, mc.mtf_confluence AS confluence,
             count(*) AS loss_count,
             round(avg(d.pnl) * 100) / 100 AS avg_loss
        WHERE loss_count >= 2
        RETURN signal, regime, confluence, loss_count, avg_loss
        ORDER BY loss_count DESC, avg_loss ASC
        LIMIT 6
        """
        try:
            with self._driver.session() as s:
                return [dict(r) for r in s.run(cypher)]
        except Exception as e:
            logger.error(f"Neo4j anti_patterns error: {e}")
            return []

    def get_time_performance(self) -> list[dict]:
        """Performance by UTC hour — finds best/worst trading windows."""
        if not self.available:
            return []
        cypher = """
        MATCH (d:Decision)-[:AT_TIME]->(tc:TimeContext)
        WHERE d.outcome <> 'pending'
        RETURN tc.hour_utc AS hour,
               tc.session AS session,
               count(*) AS total,
               sum(CASE WHEN d.pnl > 0 THEN 1 ELSE 0 END) AS wins,
               round(avg(d.pnl) * 100) / 100 AS avg_pnl
        ORDER BY hour
        """
        try:
            with self._driver.session() as s:
                return [dict(r) for r in s.run(cypher)]
        except Exception as e:
            logger.error(f"Neo4j time_performance error: {e}")
            return []

    def get_confluence_performance(self) -> list[dict]:
        """Win rate per MTF confluence type."""
        if not self.available:
            return []
        cypher = """
        MATCH (d:Decision)-[:MADE_IN]->(mc:MarketCondition)-[:HAS_CONFLUENCE]->(c:Confluence)
        WHERE d.outcome <> 'pending'
        RETURN c.name AS confluence,
               count(*) AS total,
               sum(CASE WHEN d.pnl > 0 THEN 1 ELSE 0 END) AS wins,
               round(avg(d.pnl) * 100) / 100 AS avg_pnl
        ORDER BY total DESC
        """
        try:
            with self._driver.session() as s:
                return [dict(r) for r in s.run(cypher)]
        except Exception as e:
            logger.error(f"Neo4j confluence_performance error: {e}")
            return []

    def get_memory_summary(self) -> dict:
        """High-level stats for the dashboard."""
        if not self.available:
            return {"available": False}
        cypher = """
        MATCH (d:Decision) WHERE d.outcome <> 'pending'
        RETURN count(*) AS resolved,
               sum(CASE WHEN d.pnl > 0 THEN 1 ELSE 0 END) AS wins,
               round(sum(d.pnl) * 100) / 100 AS total_pnl
        """
        cypher_pending = "MATCH (d:Decision {outcome: 'pending'}) RETURN count(*) AS pending"
        cypher_signals = "MATCH (s:Signal) RETURN count(*) AS signal_count"
        cypher_patterns = "MATCH ()-[r:CO_OCCURS_WITH]->() RETURN count(r) AS co_edges"
        try:
            with self._driver.session() as s:
                stats = dict(s.run(cypher).single() or {})
                pending = dict(s.run(cypher_pending).single() or {})
                signals = dict(s.run(cypher_signals).single() or {})
                patterns = dict(s.run(cypher_patterns).single() or {})
            total = stats.get("resolved", 0)
            wins = stats.get("wins", 0)
            return {
                "available": True,
                "total_decisions": total + pending.get("pending", 0),
                "resolved": total,
                "pending": pending.get("pending", 0),
                "wins": wins,
                "losses": total - wins,
                "win_rate": round(wins / total * 100, 1) if total > 0 else 0,
                "total_pnl": stats.get("total_pnl", 0),
                "unique_signals": signals.get("signal_count", 0),
                "co_occurrence_edges": patterns.get("co_edges", 0),
            }
        except Exception as e:
            logger.error(f"Neo4j summary error: {e}")
            return {"available": False, "error": str(e)}

    # ── Memory context for Claude prompt ─────────────────────────────────────

    def build_memory_context(
        self,
        regime: str,
        confluence: str,
        rsi_band: str,
        scorecard_bias: str,
        action_hint: str = "BUY",
    ) -> str:
        """
        Synthesize past experience into a natural-language block for Claude's prompt.
        This is the key intelligence layer — Claude reads its own past mistakes and wins.
        """
        if not self.available:
            return "Long-term memory: not connected."

        lines = ["LONG-TERM MEMORY (from past decisions in similar conditions):"]

        # 1. Similar situation outcomes
        similar = self.query_similar_situations(regime, confluence, rsi_band, scorecard_bias, action_hint)
        if similar:
            resolved = [s for s in similar if s.get("outcome") != "pending"]
            wins = [s for s in resolved if s.get("pnl", 0) > 0]
            losses = [s for s in resolved if s.get("pnl", 0) < 0]
            avg_win = sum(s["pnl"] for s in wins) / len(wins) if wins else 0
            avg_loss = sum(s["pnl"] for s in losses) / len(losses) if losses else 0
            win_rate = len(wins) / len(resolved) * 100 if resolved else 0
            lines.append(
                f"\n  Similar past {action_hint} decisions ({regime} regime, {scorecard_bias} bias, {confluence}):"
            )
            lines.append(f"  → {len(resolved)} resolved: {len(wins)} wins (avg +${avg_win:.2f}), "
                         f"{len(losses)} losses (avg ${avg_loss:.2f}) | Win rate: {win_rate:.0f}%")
            if resolved:
                signal_counts: dict = {}
                for s in wins:
                    for sig in s.get("signals") or []:
                        signal_counts[sig] = signal_counts.get(sig, 0) + 1
                if signal_counts:
                    top = sorted(signal_counts.items(), key=lambda x: x[1], reverse=True)[:3]
                    lines.append(f"  → Signals present in winning trades: {', '.join(s for s, _ in top)}")

        # 2. Best signal combos
        combos = self.get_best_signal_combos()
        if combos:
            lines.append("\n  Best performing signal combinations (historical):")
            for c in combos[:3]:
                lines.append(
                    f"  → [{c['sig1']} + {c['sig2']}]: {c['win_rate_pct']:.0f}% win rate "
                    f"over {c['total']} trades, avg P&L ${c['avg_pnl']:+.2f}"
                )

        # 3. Anti-patterns to avoid
        anti = self.get_anti_patterns()
        if anti:
            lines.append("\n  Anti-patterns (signals that consistently lose — avoid these combos):")
            for a in anti[:3]:
                lines.append(
                    f"  ⚠ [{a['signal']}] in {a['regime']} / {a['confluence']}: "
                    f"lost {a['loss_count']} times, avg ${a['avg_loss']:.2f}"
                )

        # 4. Regime-specific performance
        regime_perf = self.get_regime_performance()
        regime_rows = [r for r in regime_perf if r["regime"] == regime]
        if regime_rows:
            lines.append(f"\n  Your track record in '{regime}' markets:")
            for r in regime_rows:
                wr = round(r["wins"] / r["total"] * 100) if r["total"] > 0 else 0
                lines.append(
                    f"  → {r['action']}: {r['total']} trades, {wr}% win rate, "
                    f"total P&L ${r['total_pnl']:+.2f}"
                )

        # 5. Confluence-specific insight
        conf_perf = self.get_confluence_performance()
        conf_row = next((r for r in conf_perf if r["confluence"] == confluence), None)
        if conf_row and conf_row["total"] >= 3:
            wr = round(conf_row["wins"] / conf_row["total"] * 100)
            lines.append(
                f"\n  When MTF confluence = '{confluence}': {conf_row['total']} trades, "
                f"{wr}% win rate, avg P&L ${conf_row['avg_pnl']:+.2f}"
            )

        if len(lines) == 1:
            lines.append("  No resolved decisions yet — this is early-stage learning. Proceed with caution.")

        return "\n".join(lines)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _rsi_band(rsi: Optional[float]) -> str:
    if rsi is None:
        return "unknown"
    if rsi < 25:
        return "extreme_oversold"
    if rsi < 35:
        return "oversold"
    if rsi < 45:
        return "near_oversold"
    if rsi < 55:
        return "neutral"
    if rsi < 65:
        return "near_overbought"
    if rsi < 75:
        return "overbought"
    return "extreme_overbought"


def _volume_band(ratio: float) -> str:
    if ratio >= 2.5:
        return "very_high"
    if ratio >= 1.5:
        return "high"
    if ratio >= 0.8:
        return "normal"
    return "low"


def _bb_zone(pct: Optional[float]) -> str:
    if pct is None:
        return "unknown"
    if pct < 0.15:
        return "near_lower"
    if pct < 0.4:
        return "lower_half"
    if pct < 0.6:
        return "middle"
    if pct < 0.85:
        return "upper_half"
    return "near_upper"


def _funding_sign(rate: float) -> str:
    if rate > 0.001:
        return "very_positive"
    if rate > 0.0003:
        return "positive"
    if rate < -0.0005:
        return "negative"
    return "neutral"


def _session_label(hour_utc: int) -> str:
    if 0 <= hour_utc < 6:
        return "asia_night"
    if 6 <= hour_utc < 10:
        return "europe_open"
    if 10 <= hour_utc < 13:
        return "europe_midday"
    if 13 <= hour_utc < 17:
        return "us_open"
    if 17 <= hour_utc < 21:
        return "us_afternoon"
    return "us_night"
