import rough from "roughjs";
import {
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
  type CSSProperties,
  type ElementType,
  type ReactNode,
} from "react";

/*
 * rough.js 手繪輪廓。背景仍由 CSS 畫（文字對比才穩定），這裡只疊一層抖動的線條。
 * rough.js 會把顏色寫成 SVG 屬性，而屬性不支援 CSS 變數；所以先用代號顏色畫，
 * 畫完再把代號換成 inline style 的 var(--…)，夜讀模式切換時線條顏色才會跟著變。
 */
const STROKE_TOKEN = "#010101";
const FILL_TOKEN = "#020202";

export type SketchOptions = {
  radius?: number;
  stroke?: string;
  strokeWidth?: number;
  roughness?: number;
  fill?: string;
  fillStyle?: "solid" | "hachure" | "zigzag" | "cross-hatch" | "dots";
  inset?: number;
};

export function roundedRectPath(x: number, y: number, w: number, h: number, r: number): string {
  const rr = Math.max(0, Math.min(r, w / 2, h / 2));
  return [
    `M ${x + rr} ${y}`,
    `L ${x + w - rr} ${y}`,
    `Q ${x + w} ${y} ${x + w} ${y + rr}`,
    `L ${x + w} ${y + h - rr}`,
    `Q ${x + w} ${y + h} ${x + w - rr} ${y + h}`,
    `L ${x + rr} ${y + h}`,
    `Q ${x} ${y + h} ${x} ${y + h - rr}`,
    `L ${x} ${y + rr}`,
    `Q ${x} ${y} ${x + rr} ${y}`,
    "Z",
  ].join(" ");
}

export function drawSketch(svg: SVGSVGElement, w: number, h: number, seed: number, o: SketchOptions) {
  while (svg.firstChild) svg.removeChild(svg.firstChild);
  if (w < 4 || h < 4) return;
  const inset = o.inset ?? 1.5;
  const rc = rough.svg(svg);
  const node = rc.path(roundedRectPath(inset, inset, w - inset * 2, h - inset * 2, o.radius ?? 20), {
    seed,
    stroke: STROKE_TOKEN,
    strokeWidth: o.strokeWidth ?? 2,
    roughness: o.roughness ?? 1.1,
    bowing: 0.8,
    fill: o.fill ? FILL_TOKEN : undefined,
    fillStyle: o.fillStyle ?? "solid",
    hachureGap: 7,
    fillWeight: 1.5,
    preserveVertices: true,
  });
  applyColors(node, o.stroke ?? "var(--line-sketch)", o.fill);
  svg.appendChild(node);
}

export function applyColors(node: Element, stroke: string, fill?: string) {
  node.querySelectorAll("path").forEach((p) => {
    for (const attr of ["stroke", "fill"] as const) {
      const v = p.getAttribute(attr);
      if (v === STROKE_TOKEN) {
        p.removeAttribute(attr);
        p.style.setProperty(attr, stroke);
      } else if (v === FILL_TOKEN && fill) {
        p.removeAttribute(attr);
        p.style.setProperty(attr, fill);
      }
    }
  });
}

export function useElementSize<T extends HTMLElement>() {
  const ref = useRef<T>(null);
  const [size, setSize] = useState({ w: 0, h: 0 });
  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;
    const update = () => setSize({ w: Math.round(el.offsetWidth), h: Math.round(el.offsetHeight) });
    update();
    const ro = new ResizeObserver(update);
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  return [ref, size] as const;
}

export const randomSeed = () => Math.floor(Math.random() * 2 ** 31);

type SketchProps = SketchOptions & {
  as?: ElementType;
  className?: string;
  style?: CSSProperties;
  children?: ReactNode;
  seed?: number;
  [key: string]: unknown;
};

export function Sketch({
  as: Tag = "div",
  className,
  style,
  children,
  seed,
  radius,
  stroke,
  strokeWidth,
  roughness,
  fill,
  fillStyle,
  inset,
  ...rest
}: SketchProps) {
  const [ref, size] = useElementSize<HTMLElement>();
  const svgRef = useRef<SVGSVGElement>(null);
  const [stableSeed] = useState(() => seed ?? randomSeed());

  useEffect(() => {
    if (svgRef.current) {
      drawSketch(svgRef.current, size.w, size.h, stableSeed, { radius, stroke, strokeWidth, roughness, fill, fillStyle, inset });
    }
  }, [size.w, size.h, stableSeed, radius, stroke, strokeWidth, roughness, fill, fillStyle, inset]);

  return (
    <Tag ref={ref} className={`sketch ${className ?? ""}`} style={style} {...rest}>
      <svg ref={svgRef} className="sketch__svg" aria-hidden="true" width={size.w} height={size.h} />
      {children}
    </Tag>
  );
}
