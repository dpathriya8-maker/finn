import { describe, expect, it } from "vitest";
import { TONE, toneBox } from "@/components/brief/tone";

describe("the look of a card by its tone", () => {
  it("gives a risk a red 3px edge and a red tint, a win green, a watch amber", () => {
    expect(toneBox("bad")).toBe("border-l-[3px] border-l-bad bg-bad-tint");
    expect(toneBox("good")).toBe("border-l-[3px] border-l-good bg-good-tint");
    expect(toneBox("watch")).toBe("border-l-[3px] border-l-watch bg-watch-tint");
  });
  it("gives a neutral card no tint and a transparent edge, and keeps the plain background it was given", () => {
    expect(toneBox("neutral")).toBe("border-l-[3px] border-l-transparent");
    expect(toneBox("neutral", "bg-surface")).toBe("border-l-[3px] border-l-transparent bg-surface");
  });
  it("always pairs colour with a word, so colour is never the only signal", () => {
    expect([TONE.bad.tag, TONE.watch.tag, TONE.good.tag]).toEqual(["Risk", "Watch", "Good"]);
    expect(TONE.neutral.tag).toBe("");
  });
});
