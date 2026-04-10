import { afterAll, beforeAll, describe, expect, mock, test } from "bun:test";
import { render, screen } from "@testing-library/react";

const resetFn = mock(() => {});

beforeAll(() => {
	mock.module("@/hooks/use-incident-stream", () => ({
		useIncidentStream: () => ({
			stages: [
				{ name: "ingest", status: "done", logs: [] },
				{ name: "moderation", status: "running", logs: [] },
			],
			incidentId: null,
			severity: null,
			duplicateMatch: null,
			triageResult: null,
			ticket: null,
			error: null,
			done: false,
			submitting: true,
			resolved: false,
			ttrMinutes: null,
			moderationPassed: null,
			notifyResult: null,
			blocked: false,
			blockedReason: null,
			submit: () => {},
			dismissDuplicate: () => {},
			markResolved: () => {},
			reset: resetFn,
		}),
	}));
});

afterAll(() => {
	mock.restore();
});

const { default: Home } = await import("@/app/page");

describe("Cancel during pipeline", () => {
	test("shows Cancel button when submitting and not done", () => {
		render(<Home />);
		const cancelBtn = screen.getByRole("button", { name: /cancel/i });
		expect(cancelBtn).toBeTruthy();
	});
});
