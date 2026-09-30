import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import en from "./en.json";
import zhTW from "./zh-TW.json";
import { format, lookup } from "./index";

type Dict = { [k: string]: string | Dict };

function flatten(d: Dict, prefix = ""): Record<string, string> {
  return Object.entries(d).reduce<Record<string, string>>((acc, [k, v]) => {
    const key = prefix ? `${prefix}.${k}` : k;
    return typeof v === "string" ? { ...acc, [key]: v } : { ...acc, ...flatten(v, key) };
  }, {});
}

function sourceFiles(dir: string): string[] {
  return readdirSync(dir).flatMap((name: string) => {
    const p = join(dir, name);
    if (statSync(p).isDirectory()) return sourceFiles(p);
    return /\.tsx?$/.test(name) && !name.endsWith(".test.ts") ? [p] : [];
  });
}

const zh = flatten(zhTW as Dict);
const eng = flatten(en as Dict);
const placeholders = (s: string) => [...s.matchAll(/\{(\w+)\}/g)].map((m) => m[1]).sort();

describe("語系檔", () => {
  it("兩種語言的 key 完全一致", () => {
    expect(Object.keys(eng).sort()).toEqual(Object.keys(zh).sort());
  });

  it("每個翻譯的變數佔位符一致", () => {
    for (const key of Object.keys(zh)) expect(placeholders(eng[key]), key).toEqual(placeholders(zh[key]));
  });

  it("程式裡用到的每個 key 都存在", () => {
    const root = fileURLToPath(new URL("..", import.meta.url));
    const used = new Set<string>();
    for (const file of sourceFiles(root)) {
      for (const m of readFileSync(file, "utf8").matchAll(/\bt\(\s*"([\w.-]+)"/g)) used.add(m[1]);
    }
    expect(used.size).toBeGreaterThan(50);
    const missing = [...used].filter((k) => !(k in zh));
    expect(missing).toEqual([]);
  });

  it("動態組合的 key 也都有對應", () => {
    for (const s of ["empty", "todo", "partial", "done"]) expect(zh[`series.status_${s}`]).toBeTruthy();
    for (const s of ["queued", "ocr", "translate", "render"]) expect(zh[`job.step_${s}`]).toBeTruthy();
    for (const c of ["character", "place", "technique", "item", "other"]) expect(zh[`glossary.cat_${c}`]).toBeTruthy();
    for (const f of ["page", "scroll"]) expect(zh[`series.format_${f}`]).toBeTruthy();
    for (const l of ["ja", "zh-TW", "ko", "en", "zh"]) expect(zh[`lang.${l}`]).toBeTruthy();
  });
});

describe("lookup / format", () => {
  it("依路徑取值並代入變數", () => {
    expect(lookup(zhTW as Dict, "series.episodeLabel")).toBe("第 {n} 話");
    expect(format("第 {n} 話", { n: 3 })).toBe("第 3 話");
    expect(format("{a}{b}", { a: 1 })).toBe("1{b}");
    expect(lookup(zhTW as Dict, "series.nope")).toBeUndefined();
  });
});
