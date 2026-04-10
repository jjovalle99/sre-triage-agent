import { JSDOM } from "jsdom";

const dom = new JSDOM("<!DOCTYPE html><html><body></body></html>", {
	url: "http://localhost:3000",
	pretendToBeVisual: true,
});

Object.defineProperty(globalThis, "window", {
	value: dom.window,
	writable: true,
	configurable: true,
});
Object.defineProperty(globalThis, "document", {
	value: dom.window.document,
	writable: true,
	configurable: true,
});
Object.defineProperty(globalThis, "navigator", {
	value: dom.window.navigator,
	writable: true,
	configurable: true,
});
Object.defineProperty(globalThis, "HTMLElement", {
	value: dom.window.HTMLElement,
	writable: true,
	configurable: true,
});
Object.defineProperty(globalThis, "HTMLInputElement", {
	value: dom.window.HTMLInputElement,
	writable: true,
	configurable: true,
});
Object.defineProperty(globalThis, "HTMLTextAreaElement", {
	value: dom.window.HTMLTextAreaElement,
	writable: true,
	configurable: true,
});
Object.defineProperty(globalThis, "HTMLSelectElement", {
	value: dom.window.HTMLSelectElement,
	writable: true,
	configurable: true,
});
Object.defineProperty(globalThis, "HTMLFormElement", {
	value: dom.window.HTMLFormElement,
	writable: true,
	configurable: true,
});
Object.defineProperty(globalThis, "HTMLButtonElement", {
	value: dom.window.HTMLButtonElement,
	writable: true,
	configurable: true,
});
Object.defineProperty(globalThis, "Element", {
	value: dom.window.Element,
	writable: true,
	configurable: true,
});
Object.defineProperty(globalThis, "Node", {
	value: dom.window.Node,
	writable: true,
	configurable: true,
});
Object.defineProperty(globalThis, "DocumentFragment", {
	value: dom.window.DocumentFragment,
	writable: true,
	configurable: true,
});
Object.defineProperty(globalThis, "Event", {
	value: dom.window.Event,
	writable: true,
	configurable: true,
});
Object.defineProperty(globalThis, "CustomEvent", {
	value: dom.window.CustomEvent,
	writable: true,
	configurable: true,
});
Object.defineProperty(globalThis, "MutationObserver", {
	value: dom.window.MutationObserver,
	writable: true,
	configurable: true,
});
Object.defineProperty(globalThis, "getComputedStyle", {
	value: dom.window.getComputedStyle,
	writable: true,
	configurable: true,
});
Object.defineProperty(globalThis, "requestAnimationFrame", {
	value: (cb: FrameRequestCallback) => setTimeout(cb, 0),
	writable: true,
	configurable: true,
});
Object.defineProperty(globalThis, "cancelAnimationFrame", {
	value: clearTimeout,
	writable: true,
	configurable: true,
});

if (!dom.window.HTMLElement.prototype.scrollIntoView) {
	dom.window.HTMLElement.prototype.scrollIntoView = () => {};
}

// Must import AFTER globals are set so @testing-library finds document.body
const { cleanup } = await import("@testing-library/react");
const { afterEach } = await import("bun:test");
afterEach(cleanup);
