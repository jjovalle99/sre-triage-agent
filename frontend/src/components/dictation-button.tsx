"use client";

import { Mic, Square } from "lucide-react";
import { useCallback, useRef, useState } from "react";
import { cn } from "@/lib/utils";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

interface DictationButtonProps {
	onResult: (text: string) => void;
	disabled?: boolean;
}

/** Small mic button for voice-to-text dictation via Voxtral. */
export function DictationButton({
	onResult,
	disabled = false,
}: DictationButtonProps) {
	const [recording, setRecording] = useState(false);
	const [transcribing, setTranscribing] = useState(false);
	const [error, setError] = useState<string | null>(null);
	const recorderRef = useRef<MediaRecorder | null>(null);
	const chunksRef = useRef<Blob[]>([]);

	const toggle = useCallback(async () => {
		if (recording) {
			recorderRef.current?.stop();
			return;
		}

		setError(null);
		try {
			const stream = await navigator.mediaDevices.getUserMedia({
				audio: true,
			});
			const recorder = new MediaRecorder(stream);
			recorderRef.current = recorder;
			chunksRef.current = [];

			recorder.ondataavailable = (e) => {
				if (e.data.size > 0) chunksRef.current.push(e.data);
			};

			recorder.onstop = async () => {
				for (const track of stream.getTracks()) track.stop();
				setRecording(false);

				const blob = new Blob(chunksRef.current, { type: "audio/webm" });
				if (blob.size === 0) return;

				setTranscribing(true);
				try {
					const fd = new FormData();
					fd.set("audio", blob, "dictation.webm");
					const resp = await fetch(`${API_BASE}/api/transcribe`, {
						method: "POST",
						body: fd,
					});
					if (resp.ok) {
						const { text } = (await resp.json()) as { text: string };
						if (text.trim()) onResult(text.trim());
					} else {
						setError("Transcription failed");
					}
				} catch {
					setError("Could not reach transcription service");
				} finally {
					setTranscribing(false);
				}
			};

			recorder.start();
			setRecording(true);
		} catch {
			setError("Mic access denied");
		}
	}, [recording, onResult]);

	const busy = recording || transcribing;

	return (
		<div className="relative inline-flex">
			<button
				type="button"
				onClick={toggle}
				disabled={disabled || transcribing}
				className={cn(
					"size-7 rounded-md flex items-center justify-center transition-all",
					recording
						? "bg-destructive/20 text-destructive ring-2 ring-destructive/30 animate-pulse"
						: "text-muted-foreground hover:text-foreground hover:bg-accent",
					(disabled || transcribing) && "opacity-50 pointer-events-none",
				)}
				aria-label={recording ? "Stop dictation" : "Dictate"}
				title={recording ? "Click to stop" : "Click to dictate"}
			>
				{recording ? (
					<Square className="size-3" />
				) : (
					<Mic className="size-3.5" />
				)}
			</button>
			{transcribing && (
				<span className="absolute -top-1 -right-1 size-2 rounded-full bg-primary animate-pulse" />
			)}
			{error && !busy && (
				<span className="absolute top-full right-0 mt-1 text-[10px] text-destructive whitespace-nowrap">
					{error}
				</span>
			)}
		</div>
	);
}
