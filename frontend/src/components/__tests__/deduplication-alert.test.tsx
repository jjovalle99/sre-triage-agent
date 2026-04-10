import { describe, expect, mock, test } from "bun:test";
import { render, screen } from "@testing-library/react";
import { DeduplicationAlert } from "@/components/deduplication-alert";

describe("DeduplicationAlert", () => {
	test("renders similar incident message", () => {
		render(
			<DeduplicationAlert
				matchId="abc-123"
				similarity={0.85}
				onProceed={() => {}}
				onCancel={() => {}}
			/>,
		);
		expect(screen.getByText(/Similar incident detected/i)).toBeTruthy();
		expect(screen.getByText(/85%/)).toBeTruthy();
	});

	test("calls onProceed when proceed button clicked", () => {
		const onProceed = mock(() => {});
		render(
			<DeduplicationAlert
				matchId="abc-123"
				similarity={0.85}
				onProceed={onProceed}
				onCancel={() => {}}
			/>,
		);
		screen.getByRole("button", { name: /proceed/i }).click();
		expect(onProceed).toHaveBeenCalled();
	});

	test("calls onCancel when cancel button clicked", () => {
		const onCancel = mock(() => {});
		render(
			<DeduplicationAlert
				matchId="abc-123"
				similarity={0.85}
				onProceed={() => {}}
				onCancel={onCancel}
			/>,
		);
		screen.getByRole("button", { name: /cancel/i }).click();
		expect(onCancel).toHaveBeenCalled();
	});
});
