/** Mock “query behind the chart” strings (Claude Dashboards pattern). */
export const KPI_QUERY_BEHIND: Record<string, string> = {
  ontime: `-- On-time % (mock warehouse)
SELECT ROUND(100.0 * SUM(CASE WHEN arrived_at <= window_end THEN 1 END) / COUNT(*), 1) AS on_time_pct
FROM stops
WHERE service_date = CURRENT_DATE AND city = 'San Francisco';`,
  active: `-- Active vans
SELECT COUNT(DISTINCT vehicle_id) AS active_vans
FROM vehicle_positions
WHERE status IN ('en_route', 'delayed') AND updated_at > NOW() - INTERVAL '5 minutes';`,
  eta: `-- Median ETA to next stop
SELECT PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY eta_minutes) AS median_eta
FROM active_routes
WHERE status = 'en_route';`,
  incidents: `-- Open incidents
SELECT COUNT(*) AS open_incidents
FROM ops_alerts
WHERE resolved_at IS NULL AND severity IN ('warning', 'critical');`,
};

export function regionQueryBehind(region: string, onTimePct: number, volume: number): string {
  return `-- ${region} desk rollup (mock)
SELECT region, on_time_pct, stop_volume, open_incidents
FROM region_daily_ops
WHERE service_date = CURRENT_DATE AND region = '${region}';
-- snapshot: on_time ${onTimePct}%, volume ${volume} stops`;
}

export function hourlyVolumeQueryBehind(hourLabel: number, volume: number): string {
  return `-- Hourly volume (mock)
SELECT hour_local, stop_count
FROM hourly_stops
WHERE service_date = CURRENT_DATE AND hour_local = ${hourLabel};
-- snapshot: ${volume} stops`;
}
