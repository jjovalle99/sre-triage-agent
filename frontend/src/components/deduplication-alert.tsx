"use client";

/** Props for the DeduplicationAlert component. */
interface DeduplicationAlertProps {
	matchId: string;
	similarity: number;
	onProceed: () => void;
	onCancel: () => void;
}

/** Alert shown when a similar recent incident is detected. */
export function DeduplicationAlert({
	matchId,
	similarity,
	onProceed,
	onCancel,
}: DeduplicationAlertProps) {
	return (
		<div
			role="alert"
			className="rounded border border-yellow-500/30 bg-yellow-500/10 p-4 text-sm"
		>
			<p className="font-semibold text-yellow-400">Similar incident detected</p>
			<p className="mt-1 text-muted-foreground">
				Matches{" "}
				<a href={`/incidents/${matchId}`} className="underline text-yellow-300">
					{matchId}
				</a>{" "}
				({Math.round(similarity * 100)}% similar)
			</p>
			<div className="mt-3 flex gap-2">
				<button
					type="button"
					onClick={onProceed}
					className="rounded bg-yellow-500 px-3 py-1 text-xs text-black font-semibold"
				>
					Proceed anyway
				</button>
				<button
					type="button"
					onClick={onCancel}
					className="rounded border border-border px-3 py-1 text-xs"
				>
					Cancel
				</button>
			</div>
		</div>
	);
}
