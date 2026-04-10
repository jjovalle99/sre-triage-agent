import { describe, expect, mock, test } from "bun:test";
import { render, screen } from "@testing-library/react";
import { AttachEvidenceZone } from "@/components/attach-evidence-zone";

describe("AttachEvidenceZone", () => {
	test("renders drop zone", () => {
		render(<AttachEvidenceZone files={[]} onFilesChange={mock()} />);
		expect(screen.getByText("Drop files or click to browse")).toBeTruthy();
	});
});
