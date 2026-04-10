"use client";

import type * as React from "react";

import { cn } from "@/lib/utils";

interface LabelProps extends React.ComponentProps<"label"> {
	required?: boolean;
}

/** Form label with optional required asterisk indicator. */
function Label({ className, required, children, ...props }: LabelProps) {
	return (
		// biome-ignore lint/a11y/noLabelWithoutControl: shadcn component — control is associated via htmlFor at usage site
		<label
			data-slot="label"
			className={cn(
				"flex items-center gap-2 text-sm leading-none font-medium select-none group-data-[disabled=true]:pointer-events-none group-data-[disabled=true]:opacity-50 peer-disabled:cursor-not-allowed peer-disabled:opacity-50",
				className,
			)}
			{...props}
		>
			{children}
			{required && (
				<span className="text-destructive" aria-hidden="true">
					*
				</span>
			)}
		</label>
	);
}

export { Label };
