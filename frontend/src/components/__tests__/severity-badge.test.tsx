import { describe, expect, test } from "bun:test";
import { render, screen } from "@testing-library/react";
import { SeverityBadge } from "@/components/severity-badge";

describe("SeverityBadge", () => {
	test("renders CLASSIFYING when no severity provided", () => {
		render(<SeverityBadge severity={null} />);
		expect(screen.getByText("CLASSIFYING...")).toBeTruthy();
	});

	test("renders P0 label when severity is P0", () => {
		render(<SeverityBadge severity="P0" />);
		expect(screen.getByText("P0")).toBeTruthy();
		expect(screen.queryByText("CLASSIFYING...")).toBeNull();
	});

	test("renders P2 label when severity is P2", () => {
		render(<SeverityBadge severity="P2" />);
		expect(screen.getByText("P2")).toBeTruthy();
	});
});
