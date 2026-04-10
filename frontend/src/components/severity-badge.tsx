"use client";

import { cn } from "@/lib/utils";

/** Severity levels returned by the classification pipeline. */
export type Severity = "P0" | "P1" | "P2" | "P3";

/** Valid severity values for runtime narrowing. */
export const VALID_SEVERITIES: readonly Severity[] = ["P0", "P1", "P2", "P3"];

/** Props for the SeverityBadge component. */
interface SeverityBadgeProps {
	severity: Severity | null;
}

/** Human-readable labels per severity level. */
export const SEVERITY_LABELS: Record<Severity, string> = {
	P0: "Critical",
	P1: "High",
	P2: "Medium",
	P3: "Low",
};

/** Color styles per severity level. */
export const SEVERITY_STYLES: Record<Severity, string> = {
	P0: "bg-red-500 text-white",
	P1: "bg-orange-500 text-white",
	P2: "bg-yellow-400 text-black",
	P3: "bg-blue-400 text-white",
};

/** Displays the AI-classified severity. Pulses gray while classifying. */
export function SeverityBadge({ severity }: SeverityBadgeProps) {
	const isClassifying = severity === null;
	return (
		<span
			className={cn(
				"inline-flex items-center rounded px-2 py-0.5 text-xs font-mono font-bold transition-all duration-500",
				isClassifying
					? "bg-secondary text-muted-foreground animate-pulse"
					: `${SEVERITY_STYLES[severity]} animate-in zoom-in-75`,
			)}
		>
			{isClassifying ? "CLASSIFYING..." : severity}
		</span>
	);
}
