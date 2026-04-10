import { defineConfig } from "@playwright/test";

export default defineConfig({
	use: {
		baseURL: "http://localhost:3000",
		screenshot: "on",
	},
	testDir: "./e2e",
	outputDir: "./e2e/results",
});
