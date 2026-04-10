"use client";

import { IconChartBar, IconX } from "@tabler/icons-react";
import { useCallback, useEffect, useState } from "react";

import {
	SEVERITY_LABELS as SEV_LABELS,
	SEVERITY_STYLES as SEV_STYLES,
} from "@/components/severity-badge";

interface ModelUsage {
	prompt_tokens: number;
	completion_tokens: number;
	estimated_cost_usd: number;
}

interface StatsData {
	total_incidents: number;
	by_severity: Record<string, number>;
	by_status: Record<string, number>;
	avg_triage_duration_ms: number;
	resolved_count: number;
	token_usage: {
		by_model: Record<string, ModelUsage>;
		total_prompt_tokens: number;
		total_completion_tokens: number;
		estimated_cost_usd: number;
	};
}

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

const SEVERITY_COLORS: Record<string, string> = {
	P0: "bg-red-500",
	P1: "bg-orange-500",
	P2: "bg-yellow-400",
	P3: "bg-blue-400",
};

const STATUS_LABELS: Record<string, string> = {
	submitted: "Submitted",
	triaging: "Triaging",
	triaged: "Triaged",
	notified: "Notified",
	resolved: "Resolved",
	triage_failed: "Failed",
	ticket_created: "Ticketed",
	acknowledged: "Acked",
	in_progress: "In Progress",
};

const STATUS_COLORS: Record<string, string> = {
	submitted: "bg-muted-foreground/40",
	triaging: "bg-primary",
	triaged: "bg-primary/70",
	notified: "bg-primary/50",
	resolved: "bg-emerald-500",
	triage_failed: "bg-rose-500",
	ticket_created: "bg-primary/70",
	acknowledged: "bg-primary/50",
	in_progress: "bg-primary",
};

/** Formats a model ID into a short display name. */
function shortModel(model: string): string {
	return model
		.replace(/-latest$/, "")
		.replace("claude-sonnet-4-6", "Claude Sonnet")
		.replace("mistral-moderation-2603", "Moderation")
		.replace("mistral-medium", "Mistral Med")
		.replace("mistral-small", "Mistral Sm")
		.replace("voxtral-mini", "Voxtral");
}

/** Distribution bar with rounded segments. */
function DistributionBar({
	data,
	colors,
	total,
}: {
	data: Record<string, number>;
	colors: Record<string, string>;
	total: number;
}) {
	if (total === 0) return <div className="h-2 rounded-full bg-secondary" />;
	return (
		<div className="flex h-2 rounded-full overflow-hidden gap-px bg-secondary">
			{Object.entries(data).map(([key, count]) => (
				<div
					key={key}
					className={`${colors[key] ?? "bg-muted-foreground/40"} transition-all`}
					style={{ width: `${(count / total) * 100}%` }}
				/>
			))}
		</div>
	);
}

/** Legend in a 2-column grid with humanized labels. */
function Legend({
	data,
	colors,
	labels,
}: {
	data: Record<string, number>;
	colors: Record<string, string>;
	labels?: Record<string, string>;
}) {
	return (
		<div className="grid grid-cols-2 gap-x-3 gap-y-1.5">
			{Object.entries(data).map(([key, count]) => (
				<div key={key} className="flex items-center gap-1.5">
					<div
						className={`size-2 rounded-full ring-1 ring-white/10 flex-shrink-0 ${colors[key] ?? "bg-muted-foreground/40"}`}
					/>
					<span className="text-[11px] text-muted-foreground truncate">
						{labels?.[key] ?? key}{" "}
						<span className="font-mono text-foreground">{count}</span>
					</span>
				</div>
			))}
		</div>
	);
}

/** Severity legend using the same badge style as the main app. */
function SeverityLegend({ data }: { data: Record<string, number> }) {
	return (
		<div className="grid grid-cols-2 gap-2">
			{Object.entries(data).map(([key, count]) => {
				const style =
					SEV_STYLES[key as keyof typeof SEV_STYLES] ??
					"bg-secondary text-foreground";
				const label = SEV_LABELS[key as keyof typeof SEV_LABELS] ?? key;
				return (
					<div key={key} className="flex items-center gap-2">
						<span
							className={`text-[10px] font-mono font-bold rounded px-1.5 py-0.5 ${style}`}
						>
							{key}
						</span>
						<span className="text-[11px] text-muted-foreground">
							{label} <span className="font-mono text-foreground">{count}</span>
						</span>
					</div>
				);
			})}
		</div>
	);
}

/** Stats drawer triggered by a header icon. */
export function StatsDrawer() {
	const [open, setOpen] = useState(false);
	const [stats, setStats] = useState<StatsData | null>(null);

	const fetchStats = useCallback(async () => {
		try {
			const resp = await fetch(`${API_URL}/api/stats`);
			if (resp.ok) setStats(await resp.json());
		} catch {
			/* stats are non-critical */
		}
	}, []);

	useEffect(() => {
		if (!open) return;
		if (!stats) fetchStats();
		const id = setInterval(fetchStats, 30_000);
		return () => clearInterval(id);
	}, [open, fetchStats, stats]);

	const resolutionRate =
		stats && stats.total_incidents > 0
			? Math.round((stats.resolved_count / stats.total_incidents) * 100)
			: 0;

	const costDisplay =
		stats && stats.token_usage.estimated_cost_usd > 0
			? `$${stats.token_usage.estimated_cost_usd.toFixed(4)}`
			: "—";

	const triageDisplay =
		stats && stats.avg_triage_duration_ms > 0
			? `${(stats.avg_triage_duration_ms / 1000).toFixed(1)}s`
			: "—";

	return (
		<>
			<button
				type="button"
				onClick={() => setOpen((o) => !o)}
				className="size-8 rounded-lg flex items-center justify-center text-muted-foreground transition-colors hover:text-foreground hover:bg-accent"
				aria-label="Toggle stats"
			>
				<IconChartBar size={18} />
			</button>

			{open && (
				<>
					<button
						type="button"
						className="fixed inset-0 bg-black/50 z-40 cursor-default backdrop-blur-[2px]"
						onClick={() => setOpen(false)}
						aria-label="Close stats overlay"
					/>
					<aside className="fixed right-0 top-0 h-full w-80 bg-background border-l border-border z-50 overflow-y-auto shadow-2xl">
						<div className="flex items-center justify-between px-4 py-3 border-b border-border">
							<h2 className="text-sm font-semibold">Pipeline Metrics</h2>
							<button
								type="button"
								onClick={() => setOpen(false)}
								className="size-7 rounded flex items-center justify-center text-muted-foreground hover:text-foreground hover:bg-accent"
								aria-label="Close stats"
							>
								<IconX size={16} />
							</button>
						</div>

						{!stats ? (
							<div className="px-4 py-8 text-center text-sm text-muted-foreground">
								Loading…
							</div>
						) : (
							<div className="p-4 space-y-5">
								<div className="grid grid-cols-2 gap-3">
									<KpiCard label="Incidents" value={stats.total_incidents} />
									<KpiCard label="Resolution" value={`${resolutionRate}%`} />
									<KpiCard label="Avg Triage" value={triageDisplay} />
									<KpiCard label="Est. Cost" value={costDisplay} />
								</div>

								<div className="space-y-2">
									<h3 className="text-[10px] font-medium text-muted-foreground uppercase tracking-widest">
										Severity
									</h3>
									<DistributionBar
										data={stats.by_severity}
										colors={SEVERITY_COLORS}
										total={stats.total_incidents}
									/>
									<SeverityLegend data={stats.by_severity} />
								</div>

								<div className="space-y-2">
									<h3 className="text-[10px] font-medium text-muted-foreground uppercase tracking-widest">
										Status
									</h3>
									<DistributionBar
										data={stats.by_status}
										colors={STATUS_COLORS}
										total={stats.total_incidents}
									/>
									<Legend
										data={stats.by_status}
										colors={STATUS_COLORS}
										labels={STATUS_LABELS}
									/>
								</div>

								{Object.keys(stats.token_usage.by_model).length > 0 && (
									<div className="space-y-2">
										<h3 className="text-[10px] font-medium text-muted-foreground uppercase tracking-widest">
											Token Usage
										</h3>
										<div className="rounded-lg border border-border bg-card overflow-hidden">
											<table className="w-full text-[11px]">
												<thead>
													<tr className="text-muted-foreground border-b border-border">
														<th className="text-left px-3 py-1.5 font-medium">
															Model
														</th>
														<th className="text-right px-3 py-1.5 font-medium">
															Tokens
														</th>
														<th className="text-right px-3 py-1.5 font-medium">
															Cost
														</th>
													</tr>
												</thead>
												<tbody>
													{Object.entries(stats.token_usage.by_model).map(
														([model, usage]) => (
															<tr
																key={model}
																className="border-b border-border/50 last:border-0"
															>
																<td className="px-3 py-1.5 text-foreground">
																	{shortModel(model)}
																</td>
																<td className="px-3 py-1.5 text-right font-mono text-muted-foreground">
																	{(
																		usage.prompt_tokens +
																		usage.completion_tokens
																	).toLocaleString()}
																</td>
																<td className="px-3 py-1.5 text-right font-mono text-muted-foreground">
																	{usage.estimated_cost_usd > 0
																		? `$${usage.estimated_cost_usd.toFixed(4)}`
																		: "—"}
																</td>
															</tr>
														),
													)}
												</tbody>
											</table>
										</div>
									</div>
								)}
							</div>
						)}
					</aside>
				</>
			)}
		</>
	);
}

/** Single KPI metric card using theme variables. */
function KpiCard({ label, value }: { label: string; value: string | number }) {
	return (
		<div className="rounded-lg border border-border bg-card px-3 py-2.5">
			<p className="text-[10px] uppercase tracking-widest text-muted-foreground font-medium">
				{label}
			</p>
			<p className="text-lg font-semibold font-mono text-foreground mt-0.5">
				{value}
			</p>
		</div>
	);
}
