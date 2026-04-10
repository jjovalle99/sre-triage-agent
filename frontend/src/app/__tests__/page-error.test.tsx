import { afterAll, beforeAll, describe, expect, mock, test } from "bun:test";
import { render, screen } from "@testing-library/react";

const originalModule = await import("@/hooks/use-incident-stream");

beforeAll(() => {
	mock.module("@/hooks/use-incident-stream", () => ({
		...originalModule,
		useIncidentStream: () => ({
			stages: [],
			incidentId: null,
			severity: null,
			duplicateMatch: null,
			triageResult: null,
			ticket: null,
			error: "Validation failed: missing category",
			done: false,
			submitting: false,
			submit: () => {},
			dismissDuplicate: () => {},
			resolved: false,
			ttrMinutes: null,
			markResolved: () => {},
			moderationPassed: null,
			notifyResult: null,
		}),
	}));
});

afterAll(() => {
	mock.restore();
});

const { default: Home } = await import("@/app/page");

describe("Home page error state", () => {
	test("shows error message even when no SSE lines exist", () => {
		render(<Home />);
		expect(
			screen.getByText("Validation failed: missing category"),
		).toBeTruthy();
	});
});
