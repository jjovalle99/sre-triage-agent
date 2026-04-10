"use client";

import { useCallback, useRef, useState } from "react";

interface SSEEvent {
	event: string;
	data: Record<string, unknown>;
}

interface DuplicateMatch {
	matchId: string;
	similarity: number;
}

export interface TriageResultData {
	severity: string;
	root_cause_hypothesis: string;
	investigation_steps: string[];
	suggested_fix: string;
	relevant_files: string[];
	blast_radius: string;
	affected_services: string[];
	confidence: number;
	duration_ms?: number;
}

interface TicketInfo {
	linearId: string;
	linearUrl: string;
}

/** A single log entry within a pipeline stage. */
export interface StageLog {
	id: string;
	text: string;
	type: "info" | "error" | "dim";
}

/** Represents one stage in the pipeline with its status and logs. */
export interface PipelineStage {
	name: string;
	status: "pending" | "running" | "done" | "error";
	model?: string;
	logs: StageLog[];
	meta?: Record<string, unknown>;
}

interface IncidentStreamState {
	stages: PipelineStage[];
	incidentId: string | null;
	severity: string | null;
	transcription: string | null;
	duplicateMatch: DuplicateMatch | null;
	triageResult: TriageResultData | null;
	ticket: TicketInfo | null;
	error: string | null;
	done: boolean;
	submitting: boolean;
	resolved: boolean;
	ttrMinutes: number | null;
	moderationPassed: boolean | null;
	notifyResult: { slack: boolean; email: boolean } | null;
	blocked: boolean;
	blockedReason: string | null;
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

const INITIAL_STATE: IncidentStreamState = {
	stages: [],
	incidentId: null,
	severity: null,
	transcription: null,
	duplicateMatch: null,
	triageResult: null,
	ticket: null,
	error: null,
	done: false,
	submitting: false,
	resolved: false,
	ttrMinutes: null,
	moderationPassed: null,
	notifyResult: null,
	blocked: false,
	blockedReason: null,
};

function findOrCreateStage(
	stages: PipelineStage[],
	name: string,
): [PipelineStage[], PipelineStage] {
	const existing = stages.find((s) => s.name === name);
	if (existing) return [stages, existing];
	const stage: PipelineStage = { name, status: "pending", logs: [] };
	return [[...stages, stage], stage];
}

function updateStage(
	stages: PipelineStage[],
	name: string,
	updater: (stage: PipelineStage) => PipelineStage,
): PipelineStage[] {
	return stages.map((s) => (s.name === name ? updater(s) : s));
}

let _logId = 0;

function nextLogId(): string {
	return `log-${++_logId}`;
}

function addLog(stage: PipelineStage, log: StageLog): PipelineStage {
	return { ...stage, logs: [...stage.logs, log] };
}

/** Submits an incident via POST and consumes the SSE pipeline stream. */
export function useIncidentStream() {
	const [state, setState] = useState<IncidentStreamState>(INITIAL_STATE);
	const abortRef = useRef<AbortController | null>(null);

	const submit = useCallback(async (formData: FormData) => {
		abortRef.current?.abort();
		const controller = new AbortController();
		abortRef.current = controller;

		setState({ ...INITIAL_STATE, submitting: true });

		try {
			const resp = await fetch(`${API_BASE}/api/incidents`, {
				method: "POST",
				body: formData,
				signal: controller.signal,
			});

			if (!resp.ok) {
				const body = await resp.json();
				setState((s) => ({
					...s,
					submitting: false,
					error: body.detail?.error ?? JSON.stringify(body.detail),
				}));
				return;
			}

			const reader = resp.body?.getReader();
			if (!reader) return;

			const decoder = new TextDecoder();
			let buffer = "";

			while (true) {
				const { done, value } = await reader.read();
				if (done) break;

				buffer += decoder.decode(value, { stream: true });
				const parts = buffer.split("\n\n");
				buffer = parts.pop() ?? "";

				for (const part of parts) {
					const parsed = parseSSEBlock(part);
					if (!parsed) continue;
					setState((s) => applyEvent(s, parsed));
				}
			}
		} catch (err) {
			if (err instanceof DOMException && err.name === "AbortError") return;
			setState((s) => ({
				...s,
				submitting: false,
				error: err instanceof Error ? err.message : "Stream failed",
			}));
		}
	}, []);

	const dismissDuplicate = useCallback(() => {
		setState((s) => ({ ...s, duplicateMatch: null }));
	}, []);

	const markResolved = useCallback((ttrMinutes: number) => {
		setState((s) => ({ ...s, resolved: true, ttrMinutes }));
	}, []);

	const reset = useCallback(() => {
		abortRef.current?.abort();
		setState(INITIAL_STATE);
	}, []);

	return { ...state, submit, dismissDuplicate, markResolved, reset };
}

function parseSSEBlock(block: string): SSEEvent | null {
	let event = "";
	let data = "";
	for (const line of block.split("\n")) {
		if (line.startsWith("event: ")) event = line.slice(7).trim();
		else if (line.startsWith("data: ")) data = line.slice(6).trim();
	}
	if (!event || !data) return null;
	try {
		return { event, data: JSON.parse(data) };
	} catch {
		return { event, data: { raw: data } };
	}
}

function applyEvent(
	s: IncidentStreamState,
	parsed: SSEEvent,
): IncidentStreamState {
	const isDone = parsed.event === "done";

	if (parsed.event === "stage") {
		const name = parsed.data.stage as string;
		const status = parsed.data.status as string;
		const model = parsed.data.model as string | undefined;

		if (status === "running") {
			const [stages] = findOrCreateStage(s.stages, name);
			return {
				...s,
				stages: updateStage(stages, name, (st) => ({
					...st,
					status: "running",
					model: model ?? st.model,
				})),
			};
		}
		if (name === "ingest") {
			return {
				...s,
				stages: updateStage(s.stages, name, (st) => ({
					...addLog(st, {
						id: nextLogId(),
						text: "Incident created",
						type: "info",
					}),
					status: "done",
				})),
			};
		}
		return {
			...s,
			stages: updateStage(s.stages, name, (st) => ({
				...st,
				status: "done",
			})),
		};
	}

	if (parsed.event === "moderation") {
		const passed = parsed.data.passed as boolean;
		return {
			...s,
			moderationPassed: passed,
			stages: updateStage(s.stages, "moderation", (st) =>
				addLog(st, {
					id: nextLogId(),
					text: passed ? "Content moderation passed" : "Content FLAGGED",
					type: passed ? "info" : "error",
				}),
			),
		};
	}

	if (parsed.event === "classification") {
		const sev = parsed.data.severity as string;
		const cat = parsed.data.category as string;
		return {
			...s,
			severity: sev,
			stages: updateStage(s.stages, "classification", (st) => ({
				...addLog(st, {
					id: nextLogId(),
					text: `severity=${sev} category=${cat}`,
					type: "info",
				}),
				meta: { ...st.meta, severity: sev, category: cat },
			})),
		};
	}

	if (parsed.event === "agent") {
		const action = parsed.data.action as string;
		const tool = parsed.data.tool as string;
		return {
			...s,
			stages: updateStage(s.stages, "triage", (st) =>
				addLog(st, {
					id: nextLogId(),
					text: action,
					type: tool === "Read" ? "info" : "dim",
				}),
			),
		};
	}

	if (parsed.event === "triage") {
		return {
			...s,
			triageResult: parsed.data as unknown as TriageResultData,
			stages: updateStage(s.stages, "triage", (st) =>
				addLog(st, {
					id: nextLogId(),
					text: parsed.data.root_cause_hypothesis as string,
					type: "info",
				}),
			),
		};
	}

	if (parsed.event === "ticket") {
		const [stages] = findOrCreateStage(s.stages, "ticket");
		return {
			...s,
			ticket: {
				linearId: parsed.data.linear_id as string,
				linearUrl: parsed.data.linear_url as string,
			},
			stages: updateStage(stages, "ticket", (st) =>
				addLog(st, {
					id: nextLogId(),
					text: `Created ${parsed.data.linear_id as string}`,
					type: "info",
				}),
			),
		};
	}

	if (parsed.event === "notify") {
		return {
			...s,
			notifyResult: {
				slack: parsed.data.slack as boolean,
				email: parsed.data.email as boolean,
			},
			stages: updateStage(s.stages, "notify", (st) =>
				addLog(st, {
					id: nextLogId(),
					text: `slack: ${parsed.data.slack ? "sent" : "skipped"} · email: ${parsed.data.email ? "sent" : "skipped"}`,
					type: "info",
				}),
			),
		};
	}

	if (parsed.event === "dedup") {
		return {
			...s,
			duplicateMatch: {
				matchId: parsed.data.match_id as string,
				similarity: parsed.data.similarity as number,
			},
		};
	}

	if (parsed.event === "transcription") {
		const text = parsed.data.text as string;
		return {
			...s,
			transcription: text,
			stages: updateStage(s.stages, "transcription", (st) =>
				addLog(st, {
					id: nextLogId(),
					text,
					type: "info",
				}),
			),
		};
	}

	if (parsed.event === "image_analysis") {
		const text = parsed.data.text as string;
		return {
			...s,
			stages: updateStage(s.stages, "image_analysis", (st) =>
				addLog(st, {
					id: nextLogId(),
					text,
					type: "info",
				}),
			),
		};
	}

	if (parsed.event === "blocked") {
		const reason = parsed.data.reason as string;
		const categories = parsed.data.flagged_categories as string[] | undefined;
		const detail = categories?.length
			? `Content flagged: ${categories.join(", ")}`
			: `Blocked by ${reason}`;
		return {
			...s,
			blocked: true,
			blockedReason: detail,
			stages: updateStage(s.stages, "moderation", (st) => ({
				...addLog(st, {
					id: nextLogId(),
					text: detail,
					type: "error",
				}),
				status: "error" as const,
			})),
		};
	}

	if (parsed.event === "error") {
		const stage = parsed.data.stage as string | undefined;
		if (stage) {
			return {
				...s,
				stages: updateStage(s.stages, stage, (st) => ({
					...addLog(st, {
						id: nextLogId(),
						text: parsed.data.error as string,
						type: "error",
					}),
					status: "error" as const,
				})),
			};
		}
		return { ...s, error: parsed.data.error as string };
	}

	if (isDone) {
		return {
			...s,
			done: true,
			submitting: false,
			incidentId: parsed.data.id as string,
		};
	}

	return s;
}
