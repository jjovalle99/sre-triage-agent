import { describe, expect, mock, test } from "bun:test";
import { fireEvent, render, screen } from "@testing-library/react";
import { IncidentForm } from "@/components/incident-form";

describe("IncidentForm", () => {
	test("renders all required fields", () => {
		render(<IncidentForm onSubmit={mock()} />);
		expect(screen.getByLabelText(/^Title/)).toBeTruthy();
		expect(screen.getByLabelText(/^Description/)).toBeTruthy();
		expect(screen.getByText(/^Category/)).toBeTruthy();
		expect(screen.getByText(/^Severity Hint/)).toBeTruthy();
		expect(
			screen.getByRole("button", { name: /create incident/i }),
		).toBeTruthy();
	});

	test("submit button is disabled when fields are empty", () => {
		render(<IncidentForm onSubmit={mock()} />);
		const btn = screen.getByRole("button", { name: /create incident/i });
		expect(btn.hasAttribute("disabled")).toBe(true);
	});

	test("submit button enables when required fields filled", async () => {
		const { container } = render(<IncidentForm onSubmit={mock()} />);
		fireEvent.change(screen.getByLabelText(/^Title/), {
			target: { value: "DB timeout" },
		});
		fireEvent.change(screen.getByLabelText(/^Description/), {
			target: { value: "Connection pool exhausted" },
		});

		const selects = container.querySelectorAll("[data-slot='select-trigger']");
		fireEvent.click(selects[0]);
		const paymentOption = await screen.findByText("Payment");
		fireEvent.click(paymentOption);

		fireEvent.click(selects[1]);
		const criticalOption = await screen.findByText("Critical");
		fireEvent.click(criticalOption);

		const btn = screen.getByRole("button", { name: /create incident/i });
		expect(btn.hasAttribute("disabled")).toBe(false);
	});
});
