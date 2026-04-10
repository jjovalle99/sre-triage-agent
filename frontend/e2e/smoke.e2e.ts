import { expect, test } from "@playwright/test";

test("homepage loads with incident form", async ({ page }) => {
	await page.goto("/");
	await expect(
		page.getByRole("heading", { name: /incident triage/i }),
	).toBeVisible();
	await expect(page.getByRole("textbox", { name: /title/i })).toBeVisible();
	await expect(
		page.getByRole("textbox", { name: /description/i }),
	).toBeVisible();
	await expect(
		page.getByRole("button", { name: /create incident/i }),
	).toBeVisible();
});
