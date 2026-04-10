import { afterAll, beforeAll, describe, expect, mock, test } from "bun:test";
import { render, screen } from "@testing-library/react";

const originalModule = await import("@/hooks/use-incident-stream");

beforeAll(() => {
	mock.module("@/hooks/use-incident-stream", () => ({
		...originalModule,
		useIncidentStream: () => ({
			stages: [
				{
					name: "triage",
					status: "done",
					logs: [],
					model: "claude-sonnet-4-6",
				},
			],
			incidentId: "abc-123",
			severity: "P1",
			duplicateMatch: null,
			triageResult: {
				severity: "P1",
				root_cause_hypothesis: "Payment gateway timeout",
				investigation_steps: ["Check logs"],
				suggested_fix: "Restart service",
				relevant_files: ["src/PaymentProcessor/Program.cs"],
				blast_radius: "Limited",
				affected_services: ["PaymentProcessor"],
				confidence: 0.85,
			},
			ticket: null,
			error: null,
			done: true,
			submitting: false,
			resolved: false,
			ttrMinutes: null,
			moderationPassed: true,
			notifyResult: null,
			submit: () => {},
			dismissDuplicate: () => {},
			markResolved: () => {},
		}),
	}));
});

afterAll(() => {
	mock.restore();
});

const { default: Home } = await import("@/app/page");

describe("Home page", () => {
	test("renders Report step when done with triageResult", () => {
		render(<Home />);
		expect(screen.getByText("Report")).toBeTruthy();
		expect(screen.getAllByText("P1 High").length).toBeGreaterThan(0);
	});
});
