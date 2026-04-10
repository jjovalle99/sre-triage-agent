"use client";

import { type FormEvent, useState } from "react";
import {
	AttachEvidenceZone,
	type EvidenceFile,
} from "@/components/attach-evidence-zone";
import { DictationButton } from "@/components/dictation-button";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
	Select,
	SelectContent,
	SelectItem,
	SelectTrigger,
	SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";

const CATEGORIES = [
	{ value: "payment", label: "Payment" },
	{ value: "catalog", label: "Catalog" },
	{ value: "orders", label: "Orders" },
	{ value: "auth", label: "Auth" },
	{ value: "infrastructure", label: "Infrastructure" },
	{ value: "other", label: "Other" },
];

const SEVERITIES = [
	{ value: "critical", label: "Critical" },
	{ value: "high", label: "High" },
	{ value: "medium", label: "Medium" },
	{ value: "low", label: "Low" },
];

const CATEGORY_LABELS = Object.fromEntries(
	CATEGORIES.map((c) => [c.value, c.label]),
);
const SEVERITY_LABELS = Object.fromEntries(
	SEVERITIES.map((s) => [s.value, s.label]),
);

interface IncidentFormProps {
	onSubmit: (formData: FormData) => void;
	disabled?: boolean;
}

/** Incident submission form with title, description, category, severity, evidence, and optional email. */
export function IncidentForm({
	onSubmit,
	disabled = false,
}: IncidentFormProps) {
	const [title, setTitle] = useState("");
	const [description, setDescription] = useState("");
	const [category, setCategory] = useState("infrastructure");
	const [severityHint, setSeverityHint] = useState("low");
	const [email, setEmail] = useState("");
	const [emailError, setEmailError] = useState("");
	const [emailTouched, setEmailTouched] = useState(false);
	const [evidenceFiles, setEvidenceFiles] = useState<EvidenceFile[]>([]);

	const isValid =
		title.trim() !== "" &&
		description.trim() !== "" &&
		category !== "" &&
		severityHint !== "" &&
		!emailError;

	function validateEmail(value: string): string {
		if (!value) return "";
		return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value)
			? ""
			: "Enter a valid email address";
	}

	function handleEmailBlur() {
		setEmailTouched(true);
		setEmailError(validateEmail(email));
	}

	function handleEmailChange(value: string) {
		setEmail(value);
		if (emailTouched) {
			setEmailError(validateEmail(value));
		}
	}

	function handleSubmit(e: FormEvent) {
		e.preventDefault();
		const fd = new FormData();
		fd.set("title", title);
		fd.set("description", description);
		fd.set("category", category);
		fd.set("severity_hint", severityHint);
		fd.set("reporter_email", email);

		for (const ef of evidenceFiles) {
			if (ef.type === "audio") {
				fd.append("audio", ef.file, ef.file.name);
			} else if (ef.type === "image") {
				fd.append("image", ef.file, ef.file.name);
			} else {
				fd.append("log_file", ef.file, ef.file.name);
			}
		}

		onSubmit(fd);
	}

	return (
		<form onSubmit={handleSubmit} className="space-y-5">
			<div className="space-y-1.5">
				<div className="flex items-center justify-between">
					<Label htmlFor="title" required>
						Title
					</Label>
					<span className="text-xs text-muted-foreground tabular-nums">
						{title.length}/200
					</span>
				</div>
				<div className="relative">
					<Input
						id="title"
						placeholder="Brief incident summary"
						value={title}
						onChange={(e) => setTitle(e.target.value)}
						maxLength={200}
						disabled={disabled}
						aria-required="true"
						className="pr-9"
					/>
					<div className="absolute right-1.5 top-1/2 -translate-y-1/2">
						<DictationButton
							onResult={(text) =>
								setTitle((prev) => (prev ? `${prev} ${text}` : text))
							}
							disabled={disabled}
						/>
					</div>
				</div>
			</div>

			<div className="space-y-1.5">
				<div className="flex items-center justify-between">
					<Label htmlFor="description" required>
						Description
					</Label>
					<span className="text-xs text-muted-foreground tabular-nums">
						{description.length}/5000
					</span>
				</div>
				<div className="relative">
					<Textarea
						id="description"
						placeholder="Describe the incident in detail"
						value={description}
						onChange={(e) => setDescription(e.target.value)}
						maxLength={5000}
						rows={4}
						disabled={disabled}
						aria-required="true"
						className="pr-9"
					/>
					<div className="absolute right-1.5 top-2">
						<DictationButton
							onResult={(text) =>
								setDescription((prev) => (prev ? `${prev}\n${text}` : text))
							}
							disabled={disabled}
						/>
					</div>
				</div>
			</div>

			<div className="grid grid-cols-2 gap-3">
				<div className="space-y-1.5">
					<Label required>Category</Label>
					<Select
						value={category}
						onValueChange={(v) => setCategory(v ?? "")}
						disabled={disabled}
					>
						<SelectTrigger className="w-full" aria-required="true">
							<SelectValue placeholder="Select category">
								{(value: string | null) =>
									value ? (CATEGORY_LABELS[value] ?? value) : null
								}
							</SelectValue>
						</SelectTrigger>
						<SelectContent>
							{CATEGORIES.map((c) => (
								<SelectItem key={c.value} value={c.value}>
									{c.label}
								</SelectItem>
							))}
						</SelectContent>
					</Select>
				</div>

				<div className="space-y-1.5">
					<Label required>Severity Hint</Label>
					<Select
						value={severityHint}
						onValueChange={(v) => setSeverityHint(v ?? "")}
						disabled={disabled}
					>
						<SelectTrigger className="w-full" aria-required="true">
							<SelectValue placeholder="Select severity">
								{(value: string | null) =>
									value ? (SEVERITY_LABELS[value] ?? value) : null
								}
							</SelectValue>
						</SelectTrigger>
						<SelectContent>
							{SEVERITIES.map((s) => (
								<SelectItem key={s.value} value={s.value}>
									{s.label}
								</SelectItem>
							))}
						</SelectContent>
					</Select>
				</div>
			</div>

			<AttachEvidenceZone
				files={evidenceFiles}
				onFilesChange={setEvidenceFiles}
				disabled={disabled}
			/>

			<div className="space-y-1.5">
				<Label htmlFor="email">Notify me when resolved</Label>
				<Input
					id="email"
					type="email"
					placeholder="your@email.com"
					value={email}
					onChange={(e) => handleEmailChange(e.target.value)}
					onBlur={handleEmailBlur}
					disabled={disabled}
					aria-invalid={!!emailError || undefined}
					aria-describedby={emailError ? "email-error" : undefined}
				/>
				{emailError && (
					<p id="email-error" role="alert" className="text-xs text-destructive">
						{emailError}
					</p>
				)}
			</div>

			<Button
				type="submit"
				className="w-full h-10 text-sm font-semibold"
				disabled={disabled || !isValid}
			>
				Create Incident
			</Button>
		</form>
	);
}
