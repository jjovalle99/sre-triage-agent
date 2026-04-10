"use client";

import { CloudUpload, FileText, Image, Mic, X } from "lucide-react";
import {
	type ChangeEvent,
	type DragEvent,
	useCallback,
	useRef,
	useState,
} from "react";
import { cn } from "@/lib/utils";

const ACCEPT =
	"image/png,image/jpeg,text/plain,.log,.json,audio/wav,audio/mp3,audio/mpeg,audio/webm,audio/mp4,audio/aac,video/mp4,.m4a";

/** A file attached by the user with its classified type. */
export interface EvidenceFile {
	file: File;
	type: "image" | "log" | "audio";
}

function classifyFile(file: File): EvidenceFile["type"] {
	if (file.type.startsWith("image/")) return "image";
	if (file.type.startsWith("audio/") || file.type === "video/mp4")
		return "audio";
	if (file.name.match(/\.(m4a|mp4|aac)$/i)) return "audio";
	return "log";
}

const TYPE_ICONS = {
	image: Image,
	log: FileText,
	audio: Mic,
} as const;

interface AttachEvidenceZoneProps {
	files: EvidenceFile[];
	onFilesChange: (files: EvidenceFile[]) => void;
	disabled?: boolean;
}

/** Unified drop zone for images, logs, and audio files. */
export function AttachEvidenceZone({
	files,
	onFilesChange,
	disabled = false,
}: AttachEvidenceZoneProps) {
	const [dragOver, setDragOver] = useState(false);
	const fileInputRef = useRef<HTMLInputElement>(null);

	const addFiles = useCallback(
		(incoming: FileList) => {
			const existingNames = new Set(files.map((f) => f.file.name));
			let updated = [...files];

			for (const file of incoming) {
				if (existingNames.has(file.name)) continue;
				const type = classifyFile(file);
				if (type === "audio" && updated.some((f) => f.type === "audio")) {
					updated = updated.filter((f) => f.type !== "audio");
				}
				updated.push({ file, type });
				existingNames.add(file.name);
			}
			onFilesChange(updated);
		},
		[files, onFilesChange],
	);

	const handleDrop = useCallback(
		(e: DragEvent) => {
			e.preventDefault();
			setDragOver(false);
			if (disabled || !e.dataTransfer.files.length) return;
			addFiles(e.dataTransfer.files);
		},
		[disabled, addFiles],
	);

	const handleFileInput = useCallback(
		(e: ChangeEvent<HTMLInputElement>) => {
			if (e.target.files?.length) addFiles(e.target.files);
		},
		[addFiles],
	);

	const removeFile = useCallback(
		(name: string) => {
			onFilesChange(files.filter((f) => f.file.name !== name));
		},
		[files, onFilesChange],
	);

	return (
		<div className="space-y-2">
			<button
				type="button"
				onClick={() => fileInputRef.current?.click()}
				onDragOver={(e) => {
					e.preventDefault();
					setDragOver(true);
				}}
				onDragLeave={() => setDragOver(false)}
				onDrop={handleDrop}
				disabled={disabled}
				className={cn(
					"w-full flex flex-col items-center justify-center gap-1.5 rounded-lg border border-dashed px-4 py-5 transition-all cursor-pointer",
					dragOver
						? "border-primary bg-primary/10 scale-[1.01]"
						: "border-border hover:border-ring/50 hover:bg-accent/50",
					disabled && "opacity-50 pointer-events-none",
				)}
			>
				<CloudUpload
					className={cn(
						"size-5 transition-colors",
						dragOver ? "text-primary" : "text-muted-foreground",
					)}
				/>
				<span className="text-sm text-muted-foreground">
					Drop files or click to browse
				</span>
				<span className="text-xs text-muted-foreground/60">
					Images, logs, or audio
				</span>
			</button>

			<input
				ref={fileInputRef}
				type="file"
				accept={ACCEPT}
				multiple
				className="hidden"
				onChange={handleFileInput}
			/>

			{files.length > 0 && (
				<div className="flex flex-wrap gap-2">
					{files.map((ef) => {
						const Icon = TYPE_ICONS[ef.type];
						return (
							<span
								key={ef.file.name}
								className="inline-flex items-center gap-1.5 rounded-md bg-card border border-border px-2 py-1 text-xs"
							>
								<Icon className="size-3 text-muted-foreground" />
								<span className="max-w-[120px] truncate">{ef.file.name}</span>
								<button
									type="button"
									onClick={() => removeFile(ef.file.name)}
									className="text-muted-foreground hover:text-foreground transition-colors"
									aria-label={`Remove ${ef.file.name}`}
								>
									<X className="size-3" />
								</button>
							</span>
						);
					})}
				</div>
			)}
		</div>
	);
}
