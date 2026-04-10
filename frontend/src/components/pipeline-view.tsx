"use client";

import {
	SiClaude,
	SiLinear,
	SiMistralai,
} from "@icons-pack/react-simple-icons";
import {
	CheckCircle2,
	ChevronRight,
	Circle,
	Loader2,
	Mail,
	XCircle,
} from "lucide-react";
import { useCallback, useState } from "react";
import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { SEVERITY_LABELS, type Severity } from "@/components/severity-badge";
import type {
	PipelineStage,
	TriageResultData,
} from "@/hooks/use-incident-stream";
import { cn } from "@/lib/utils";

const REMARK_PLUGINS = [remarkGfm];

/** Slack brand logo with official colors. */
function SlackIcon({ size = 16 }: { size?: number }) {
	return (
		<svg
			width={size}
			height={size}
			viewBox="0 0 24 24"
			fill="none"
			aria-hidden="true"
		>
			<path
				d="M5.042 15.165a2.528 2.528 0 0 1-2.52 2.523A2.528 2.528 0 0 1 0 15.165a2.527 2.527 0 0 1 2.522-2.52h2.52v2.52zM6.313 15.165a2.527 2.527 0 0 1 2.521-2.52 2.527 2.527 0 0 1 2.521 2.52v6.313A2.528 2.528 0 0 1 8.834 24a2.528 2.528 0 0 1-2.521-2.522v-6.313z"
				fill="#E01E5A"
			/>
			<path
				d="M8.834 5.042a2.528 2.528 0 0 1-2.521-2.52A2.528 2.528 0 0 1 8.834 0a2.528 2.528 0 0 1 2.521 2.522v2.52H8.834zM8.834 6.313a2.528 2.528 0 0 1 2.521 2.521 2.528 2.528 0 0 1-2.521 2.521H2.522A2.528 2.528 0 0 1 0 8.834a2.528 2.528 0 0 1 2.522-2.521h6.312z"
				fill="#36C5F0"
			/>
			<path
				d="M18.956 8.834a2.528 2.528 0 0 1 2.522-2.521A2.528 2.528 0 0 1 24 8.834a2.528 2.528 0 0 1-2.522 2.521h-2.522V8.834zM17.688 8.834a2.528 2.528 0 0 1-2.523 2.521 2.527 2.527 0 0 1-2.52-2.521V2.522A2.527 2.527 0 0 1 15.165 0a2.528 2.528 0 0 1 2.523 2.522v6.312z"
				fill="#2EB67D"
			/>
			<path
				d="M15.165 18.956a2.528 2.528 0 0 1 2.523 2.522A2.528 2.528 0 0 1 15.165 24a2.527 2.527 0 0 1-2.52-2.522v-2.522h2.52zM15.165 17.688a2.527 2.527 0 0 1-2.52-2.523 2.526 2.526 0 0 1 2.52-2.52h6.313A2.527 2.527 0 0 1 24 15.165a2.528 2.528 0 0 1-2.522 2.523h-6.313z"
				fill="#ECB22E"
			/>
		</svg>
	);
}

const STATUS_ICONS = {
	pending: Circle,
	running: Loader2,
	done: CheckCircle2,
	error: XCircle,
} as const;

const STAGE_LABELS: Record<string, string> = {
	ingest: "Ingest",
	transcription: "Transcription",
	image_analysis: "Image Analysis",
	moderation: "Moderation",
	classification: "Classification",
	dedup: "Deduplication",
	triage: "Triage Agent",
	ticket: "Ticket",
	notify: "Notify",
};

const LOG_MAX_HEIGHT = 192;

interface PipelineViewProps {
	stages: PipelineStage[];
	severity: string | null;
	ticket: { linearId: string; linearUrl: string } | null;
	notifyResult: { slack: boolean; email: boolean } | null;
	triageResult: TriageResultData | null;
	done: boolean;
	incidentId: string | null;
}

/** Severity badge with full label (e.g. "P0 Critical"). */
function SeverityBadge({ severity }: { severity: string }) {
	return (
		<span
			className={cn(
				"text-[10px] font-bold uppercase tracking-wide px-2 py-0.5 rounded",
				severity === "P0" && "bg-red-500 text-white",
				severity === "P1" && "bg-orange-500 text-white",
				severity === "P2" && "bg-yellow-400 text-black",
				severity === "P3" && "bg-blue-400 text-white",
			)}
		>
			{severity} {SEVERITY_LABELS[severity as Severity] ?? ""}
		</span>
	);
}

/** GitHub Actions-style pipeline visualization with collapsible stages and inline report. */
export function PipelineView({
	stages,
	severity,
	ticket,
	notifyResult,
	triageResult,
	done,
	incidentId,
}: PipelineViewProps) {
	const [manualOpen, setManualOpen] = useState<Set<string>>(new Set());
	const scrollToBottom = useCallback((el: HTMLDivElement | null) => {
		el?.scrollTo({ top: el.scrollHeight, behavior: "smooth" });
	}, []);

	const toggle = (name: string) => {
		setManualOpen((prev) => {
			const next = new Set(prev);
			if (next.has(name)) next.delete(name);
			else next.add(name);
			return next;
		});
	};

	const showReport = done && triageResult;
	const reportOpen = manualOpen.has("report");

	return (
		<div className="flex flex-col gap-0.5">
			{stages.map((stage, i) => {
				const Icon = STATUS_ICONS[stage.status];
				const label = STAGE_LABELS[stage.name] ?? stage.name;
				const isOpen = stage.status === "running" || manualOpen.has(stage.name);
				const hasLogs = stage.logs.length > 0;

				return (
					<div key={stage.name}>
						{i > 0 && (
							<div
								className={cn(
									"w-px h-1.5 ml-[13px]",
									stage.status !== "pending" ? "bg-foreground/10" : "bg-border",
								)}
							/>
						)}
						<div
							className={cn(
								"rounded-lg border transition-all",
								stage.status === "running" &&
									"border-foreground/20 bg-foreground/[0.03]",
								stage.status === "done" && "border-border bg-card/30",
								stage.status === "pending" && "border-border/50 bg-transparent",
								stage.status === "error" &&
									"border-destructive/30 bg-destructive/5",
							)}
						>
							<button
								type="button"
								className={cn(
									"w-full flex items-center gap-2.5 px-3 py-2.5 text-left",
									hasLogs && stage.status !== "running" && "cursor-pointer",
								)}
								onClick={() =>
									hasLogs && stage.status !== "running" && toggle(stage.name)
								}
							>
								<Icon
									className={cn(
										"size-5 flex-shrink-0",
										stage.status === "done" && "text-emerald-500",
										stage.status === "running" &&
											"text-foreground animate-spin",
										stage.status === "pending" && "text-muted-foreground/30",
										stage.status === "error" && "text-destructive",
									)}
								/>
								<span
									className={cn(
										"text-sm font-medium flex-1 truncate",
										stage.status === "done" && "text-muted-foreground",
										stage.status === "running" && "text-foreground",
										stage.status === "pending" && "text-muted-foreground/40",
										stage.status === "error" && "text-destructive/80",
									)}
								>
									{label}
								</span>

								<div className="flex items-center gap-2 flex-shrink-0">
									{stage.name === "classification" && severity && (
										<SeverityBadge severity={severity} />
									)}

									{stage.name === "moderation" && stage.status === "done" && (
										<span className="text-[10px] font-semibold px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-500 border border-emerald-500/20">
											PASS
										</span>
									)}
									{stage.name === "moderation" && stage.status === "error" && (
										<span className="text-[10px] font-semibold px-2 py-0.5 rounded bg-destructive/10 text-destructive border border-destructive/20">
											FLAGGED
										</span>
									)}

									{stage.name === "ticket" && ticket && (
										<>
											<SiLinear className="size-4" color="#5e6ad2" />
											<a
												href={ticket.linearUrl}
												target="_blank"
												rel="noopener noreferrer"
												onClick={(e) => e.stopPropagation()}
												className="text-[11px] font-medium px-2 py-0.5 rounded bg-[#5e6ad2]/10 text-[#818cf8] border border-[#5e6ad2]/20 hover:bg-[#5e6ad2]/20 transition-colors"
											>
												{ticket.linearId}
											</a>
										</>
									)}

									{stage.name === "notify" && notifyResult && (
										<div className="flex items-center gap-2">
											{notifyResult.slack && <SlackIcon />}
											{notifyResult.email && (
												<Mail className="size-4 text-foreground/70" />
											)}
										</div>
									)}

									{stage.model && stage.status !== "pending" && (
										<span className="text-[11px] font-mono text-muted-foreground/70 hidden sm:inline-flex items-center gap-1.5">
											{stage.model.includes("claude") && (
												<SiClaude className="size-3" color="#D97757" />
											)}
											{(stage.model.includes("mistral") ||
												stage.model.includes("voxtral")) && (
												<SiMistralai className="size-3" color="#FA520F" />
											)}
											{stage.model}
										</span>
									)}

									{hasLogs && stage.status === "done" && (
										<ChevronRight
											className={cn(
												"size-3.5 text-muted-foreground/30 transition-transform",
												isOpen && "rotate-90",
											)}
										/>
									)}
								</div>
							</button>

							{isOpen && hasLogs && (
								<div className="pb-2.5 pl-[42px] pr-3">
									<div
										ref={scrollToBottom}
										className="overflow-y-auto font-mono text-[11px] leading-relaxed space-y-px"
										style={{
											maxHeight:
												stage.name === "transcription" ? 400 : LOG_MAX_HEIGHT,
										}}
									>
										{stage.logs.map((log) => (
											<div
												key={log.id}
												className={cn(
													log.type === "info" && "text-foreground/70",
													log.type === "dim" &&
														"text-muted-foreground/40 truncate",
													log.type === "error" && "text-destructive/80",
												)}
											>
												{log.text}
											</div>
										))}
									</div>
								</div>
							)}
						</div>
					</div>
				);
			})}

			{showReport && (
				<>
					<div className="w-px h-1.5 ml-[13px] bg-foreground/10" />
					<div className="rounded-lg border border-border bg-card">
						<button
							type="button"
							className="w-full flex items-center gap-2.5 px-3 py-2.5 text-left cursor-pointer"
							onClick={() => toggle("report")}
						>
							<CheckCircle2 className="size-5 text-emerald-500 flex-shrink-0" />
							<span className="text-sm font-semibold text-foreground flex-1">
								Report
							</span>
							<div className="flex items-center gap-2 flex-shrink-0">
								{triageResult.duration_ms != null &&
									triageResult.duration_ms > 0 && (
										<span className="text-[10px] font-mono text-muted-foreground/60">
											{(triageResult.duration_ms / 1000).toFixed(1)}s
										</span>
									)}
								{severity && <SeverityBadge severity={severity} />}
								<ChevronRight
									className={cn(
										"size-3.5 text-muted-foreground/30 transition-transform",
										reportOpen && "rotate-90",
									)}
								/>
							</div>
						</button>

						{reportOpen && (
							<div className="border-t border-border/50 px-4 pb-4 pl-[42px] pt-4 max-h-[500px] overflow-y-auto prose prose-sm max-w-none report-prose">
								<Markdown remarkPlugins={REMARK_PLUGINS}>
									{buildReportMarkdown(triageResult, incidentId)}
								</Markdown>
							</div>
						)}
					</div>
				</>
			)}
		</div>
	);
}

function buildReportMarkdown(
	triage: TriageResultData,
	incidentId: string | null,
): string {
	const lines: string[] = [];

	lines.push("### Root Cause\n");
	lines.push(triage.root_cause_hypothesis);

	lines.push("\n### Investigation Steps\n");
	for (const step of triage.investigation_steps) {
		const cleaned = step.replace(/^\d+[.)]\s*/, "");
		lines.push(`1. ${cleaned}`);
	}

	lines.push("\n### Suggested Fix\n");
	lines.push(triage.suggested_fix);

	if (triage.affected_services.length > 0) {
		lines.push("\n### Affected Services\n");
		lines.push(triage.affected_services.map((s) => `\`${s}\``).join(" · "));
	}

	if (triage.relevant_files.length > 0) {
		lines.push("\n### Relevant Files\n");
		for (const file of triage.relevant_files) {
			lines.push(`- \`${file}\``);
		}
	}

	if (incidentId) {
		lines.push(`\n---\n\nIncident ID: \`${incidentId}\``);
	}

	return lines.join("\n");
}
