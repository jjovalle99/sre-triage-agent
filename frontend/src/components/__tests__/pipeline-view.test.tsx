import { describe, expect, test } from "bun:test";
import { fireEvent, render, screen } from "@testing-library/react";
import { PipelineView } from "@/components/pipeline-view";
import type {
	PipelineStage,
	TriageResultData,
} from "@/hooks/use-incident-stream";

const mockTriage: TriageResultData = {
	severity: "P1",
	root_cause_hypothesis: "Connection pool exhaustion in PaymentProcessor",
	investigation_steps: ["Check logs", "Verify pool config"],
	suggested_fix: "Increase pool size",
	relevant_files: ["src/PaymentProcessor/Program.cs"],
	blast_radius: "PaymentProcessor and Ordering.API",
	affected_services: ["PaymentProcessor", "Ordering.API"],
	confidence: 0.85,
};

const doneStages: PipelineStage[] = [
	{ name: "triage", status: "done", logs: [] },
];

describe("PipelineView report markdown", () => {
	test("report container uses prose without prose-invert or inline modifiers", () => {
		const { container } = render(
			<PipelineView
				stages={doneStages}
				severity="P1"
				ticket={null}
				notifyResult={null}
				triageResult={mockTriage}
				done={true}
				incidentId="test-id"
			/>,
		);

		const reportButton = screen.getByRole("button", { name: /report/i });
		fireEvent.click(reportButton);

		const proseContainer = container.querySelector(".prose");
		expect(proseContainer).not.toBeNull();
		const classes = proseContainer?.className;
		expect(classes).not.toContain("prose-invert");
		expect(classes).not.toContain("prose-headings:");
		expect(classes).not.toContain("prose-p:");
		expect(classes).not.toContain("prose-code:");
		expect(classes).not.toContain("prose-pre:");
		expect(classes).not.toContain("prose-li:");
	});

	test("suggested fix renders as paragraph, not code block", () => {
		const { container } = render(
			<PipelineView
				stages={doneStages}
				severity="P1"
				ticket={null}
				notifyResult={null}
				triageResult={mockTriage}
				done={true}
				incidentId="test-id"
			/>,
		);

		const reportButton = screen.getByRole("button", { name: /report/i });
		fireEvent.click(reportButton);

		const proseContainer = container.querySelector(".prose");
		expect(proseContainer).not.toBeNull();
		const html = proseContainer?.innerHTML;
		expect(html).not.toContain("<pre>");
	});

	test("renders GFM table when present in triage data", () => {
		const triageWithTable: TriageResultData = {
			...mockTriage,
			root_cause_hypothesis:
				"Summary:\n\n| Service | Status |\n|---------|--------|\n| Payment | Down |\n| Orders | Degraded |",
		};

		const { container } = render(
			<PipelineView
				stages={doneStages}
				severity="P1"
				ticket={null}
				notifyResult={null}
				triageResult={triageWithTable}
				done={true}
				incidentId="test-id"
			/>,
		);

		const reportButton = screen.getByRole("button", { name: /report/i });
		fireEvent.click(reportButton);

		const table = container.querySelector("table");
		expect(table).not.toBeNull();
	});
});
