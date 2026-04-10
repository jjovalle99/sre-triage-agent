"use client";

import { useEffect } from "react";
import { DeduplicationAlert } from "@/components/deduplication-alert";
import { IncidentForm } from "@/components/incident-form";
import { ManualResolveButton } from "@/components/manual-resolve-button";
import { PipelineView } from "@/components/pipeline-view";
import {
	SEVERITY_LABELS,
	SEVERITY_STYLES,
	type Severity,
	VALID_SEVERITIES,
} from "@/components/severity-badge";
import { StatsDrawer } from "@/components/stats-drawer";
import { useIncidentStream } from "@/hooks/use-incident-stream";
import { cn } from "@/lib/utils";

export default function Home() {
	useEffect(() => {
		navigator.mediaDevices?.getUserMedia({ audio: true }).then(
			(stream) => {
				for (const track of stream.getTracks()) track.stop();
			},
			() => {},
		);
	}, []);

	const {
		stages,
		submit,
		done,
		incidentId,
		severity,
		duplicateMatch,
		dismissDuplicate,
		triageResult,
		ticket,
		error,
		submitting,
		resolved,
		ttrMinutes,
		markResolved,
		notifyResult,
		blocked,
		blockedReason,
		reset,
	} = useIncidentStream();
	const showResults = submitting || stages.length > 0 || !!error;
	const parsedSeverity =
		severity && (VALID_SEVERITIES as readonly string[]).includes(severity)
			? (severity as Severity)
			: null;

	return (
		<div className="flex flex-col flex-1">
			<header className="border-b border-border">
				<div className="max-w-[1400px] mx-auto px-11 py-4 flex items-center gap-3">
					<div className="size-8 rounded-lg bg-primary/20 flex items-center justify-center flex-shrink-0">
						<span className="text-primary text-sm font-bold font-mono">
							SRE
						</span>
					</div>

					<div className="flex items-center gap-3 flex-1 min-w-0">
						<h1
							className={cn(
								"font-semibold tracking-tight truncate",
								showResults ? "text-[15px] text-muted-foreground" : "text-xl",
							)}
						>
							Incident Triage
						</h1>

						{done && incidentId && (
							<>
								{parsedSeverity && (
									<span
										className={cn(
											"text-[10px] font-bold uppercase px-2 py-0.5 rounded flex-shrink-0",
											SEVERITY_STYLES[parsedSeverity],
										)}
									>
										{parsedSeverity} {SEVERITY_LABELS[parsedSeverity]}
									</span>
								)}
								<span className="text-xs font-mono text-muted-foreground/50 hidden sm:inline flex-shrink-0">
									{incidentId.slice(0, 8)}
								</span>
							</>
						)}

						{showResults && (
							<div className="ml-auto flex-shrink-0 flex items-center gap-2">
								{done && incidentId && (
									<>
										{blocked ? (
											<span className="text-xs font-medium text-destructive bg-destructive/10 px-3 py-1.5 rounded-lg border border-destructive/20">
												Blocked
											</span>
										) : resolved ? (
											<span className="text-xs font-medium text-emerald-500 bg-emerald-500/10 px-3 py-1.5 rounded-lg border border-emerald-500/20">
												Resolved{ttrMinutes ? ` in ${ttrMinutes}m` : ""}
											</span>
										) : (
											<ManualResolveButton
												incidentId={incidentId}
												onResolved={markResolved}
											/>
										)}
										<button
											type="button"
											onClick={reset}
											className="text-xs font-medium px-3 py-1.5 rounded-lg border border-border bg-card text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
										>
											+ New
										</button>
									</>
								)}
								{submitting && !done && (
									<button
										type="button"
										onClick={reset}
										className="text-xs font-medium px-3 py-1.5 rounded-lg border border-destructive/30 bg-destructive/10 text-destructive transition-colors hover:bg-destructive/20"
									>
										Cancel
									</button>
								)}
							</div>
						)}
					</div>
					<StatsDrawer />
				</div>
			</header>
			<main
				className={`flex flex-col md:flex-row flex-1 max-w-[1400px] mx-auto w-full px-5 pt-8 pb-5 ${showResults ? "" : "justify-center"}`}
			>
				<section
					className={`p-6 transition-all ${showResults ? "w-full md:w-[35%] md:border-r border-b md:border-b-0 border-border" : "w-full max-w-xl mx-auto"}`}
				>
					<IncidentForm onSubmit={submit} disabled={submitting && !done} />
				</section>
				{showResults && (
					<section className="w-full md:w-[65%] p-6 space-y-4 overflow-y-auto">
						<PipelineView
							stages={stages}
							severity={severity}
							ticket={ticket}
							notifyResult={notifyResult}
							triageResult={triageResult}
							done={done}
							incidentId={incidentId}
						/>

						{blocked && blockedReason && (
							<div className="rounded-lg border border-destructive/30 bg-destructive/5 px-4 py-3 space-y-1">
								<p className="text-sm font-medium text-destructive">
									Incident Blocked
								</p>
								<p className="text-xs text-destructive/70">
									{blockedReason}. The incident was saved but triage was not
									performed. Please review and resubmit with appropriate
									content.
								</p>
							</div>
						)}

						{duplicateMatch && (
							<DeduplicationAlert
								matchId={duplicateMatch.matchId}
								similarity={duplicateMatch.similarity}
								onProceed={dismissDuplicate}
								onCancel={dismissDuplicate}
							/>
						)}

						{error && (
							<div className="rounded-lg border border-destructive/50 bg-destructive/10 px-4 py-3">
								<p className="text-sm text-destructive">{error}</p>
							</div>
						)}
					</section>
				)}
			</main>
		</div>
	);
}
