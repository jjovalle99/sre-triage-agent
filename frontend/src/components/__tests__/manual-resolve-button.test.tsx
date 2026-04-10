import { describe, expect, mock, test } from "bun:test";
import { fireEvent, render, screen } from "@testing-library/react";
import { ManualResolveButton } from "@/components/manual-resolve-button";

describe("ManualResolveButton", () => {
	test("renders Mark Resolved button", () => {
		render(<ManualResolveButton incidentId="test-id" onResolved={() => {}} />);
		expect(screen.getByText("Mark Resolved")).toBeTruthy();
	});

	test("calls onResolved after successful resolve", async () => {
		const onResolved = mock(() => {});
		const fetchMock = mock(() =>
			Promise.resolve({
				ok: true,
				json: () => Promise.resolve({ ttr_minutes: 42 }),
			} as unknown as Response),
		);
		globalThis.fetch = fetchMock;

		render(
			<ManualResolveButton incidentId="test-id" onResolved={onResolved} />,
		);

		fireEvent.click(screen.getByText("Mark Resolved"));

		await new Promise((r) => setTimeout(r, 50));

		expect(fetchMock).toHaveBeenCalledTimes(1);
		expect(onResolved).toHaveBeenCalledTimes(1);
	});
});
