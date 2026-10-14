import { describe, expect, it } from "vitest";
import { historyActionForKeyboardEvent } from "./App";

describe("history keyboard shortcuts", () => {
  it("maps command/ctrl-z and shifted variants to project history actions", () => {
    expect(historyActionForKeyboardEvent(new KeyboardEvent("keydown", { key: "z", metaKey: true }))).toBe("undo");
    expect(historyActionForKeyboardEvent(new KeyboardEvent("keydown", { key: "Z", ctrlKey: true, shiftKey: true }))).toBe("redo");
  });

  it("does not intercept native editing shortcuts inside form controls", () => {
    const input = document.createElement("input");
    document.body.append(input);
    const event = new KeyboardEvent("keydown", { key: "z", metaKey: true, bubbles: true });
    input.addEventListener("keydown", (keyboardEvent) => {
      expect(historyActionForKeyboardEvent(keyboardEvent)).toBeUndefined();
    });
    input.dispatchEvent(event);
    input.remove();
  });

  it("ignores unrelated modified keys", () => {
    expect(historyActionForKeyboardEvent(new KeyboardEvent("keydown", { key: "z" }))).toBeUndefined();
    expect(historyActionForKeyboardEvent(new KeyboardEvent("keydown", { key: "z", metaKey: true, altKey: true }))).toBeUndefined();
  });
});
