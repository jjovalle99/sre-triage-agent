import { useCallback, useState } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

interface ManualResolveButtonProps {
	incidentId: string;
	onResolved: (ttrMinutes: number) => void;
}

/** Fallback button to manually resolve an incident without the Linear webhook. */
export function ManualResolveButton({
	incidentId,
	onResolved,
}: ManualResolveButtonProps) {
	const [loading, setLoading] = useState(false);

	const handleResolve = useCallback(async () => {
		setLoading(true);
		try {
			const resp = await fetch(
				`${API_BASE}/api/incidents/${incidentId}/resolve`,
				{ method: "POST" },
			);
			if (resp.ok) {
				const data = await resp.json();
				onResolved(data.ttr_minutes ?? 0);
			}
		} finally {
			setLoading(false);
		}
	}, [incidentId, onResolved]);

	return (
		<button
			type="button"
			onClick={handleResolve}
			disabled={loading}
			className="rounded-lg border border-emerald-500/30 bg-emerald-500/10 px-3 py-1.5 text-xs font-medium text-emerald-400 transition-colors hover:bg-emerald-500/20 disabled:opacity-50"
		>
			{loading ? "Resolving..." : "Mark Resolved"}
		</button>
	);
}
