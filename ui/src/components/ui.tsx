import rough from "roughjs";
import { useEffect, useRef, useState, type ButtonHTMLAttributes, type ReactNode } from "react";
import { useAssetUrl } from "../api/hooks";
import { applyColors, randomSeed, Sketch, useElementSize } from "./Sketch";

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "ghost" | "quiet";
  size?: "md" | "sm";
};

export function Button({ variant = "ghost", size = "md", className, children, ...rest }: ButtonProps) {
  // 按鈕第一個子元素是手繪輪廓的 SVG；明確給名稱，輔助工具才一定唸得出按鈕文字
  const label = typeof children === "string" ? children : undefined;
  return (
    <Sketch
      as="button"
      type="button"
      radius={999}
      strokeWidth={1.8}
      roughness={variant === "quiet" ? 0.6 : 1}
      className={`btn btn--${variant} btn--${size} ${className ?? ""}`}
      aria-label={label}
      {...rest}
    >
      <span className="btn__label">{children}</span>
    </Sketch>
  );
}

export function Card({ children, className, tape }: { children: ReactNode; className?: string; tape?: "rose" | "butter" | "sage" }) {
  return (
    <Sketch className={`card ${className ?? ""}`} radius={20}>
      {tape && <Tape color={tape} />}
      {children}
    </Sketch>
  );
}

export function Tape({ color = "rose", side = "left" }: { color?: "rose" | "butter" | "sage"; side?: "left" | "right" }) {
  return <span className={`tape tape--${color} tape--${side}`} aria-hidden="true" />;
}

export function Sticker({ children, color = "butter" }: { children: ReactNode; color?: "butter" | "rose" | "sage" }) {
  return <span className={`sticker sticker--${color}`}>{children}</span>;
}

/** 手繪進度條：外框與填色都用 rough.js，填色用斜線（hachure）。 */
export function SketchProgress({ value, label }: { value: number; label: string }) {
  const [ref, size] = useElementSize<HTMLDivElement>();
  const svgRef = useRef<SVGSVGElement>(null);
  const [seed] = useState(randomSeed);
  const v = Math.max(0, Math.min(1, value));

  useEffect(() => {
    const svg = svgRef.current;
    if (!svg || size.w < 8) return;
    while (svg.firstChild) svg.removeChild(svg.firstChild);
    const rc = rough.svg(svg);
    const h = size.h - 4;
    if (v > 0) {
      const fill = rc.rectangle(3, 3, Math.max(6, (size.w - 6) * v), h - 2, {
        seed, stroke: "none", fill: "#020202", fillStyle: "hachure", hachureGap: 5, fillWeight: 2.2, roughness: 1.4,
      });
      // 斜線填色在 rough.js 裡是以 stroke 畫出，applyColors 會把代號顏色換成 --progress-fill
      applyColors(fill, "none", "var(--progress-fill)");
      svg.appendChild(fill);
    }
    const frame = rc.rectangle(2, 2, size.w - 4, h, { seed: seed + 1, stroke: "#010101", strokeWidth: 1.6, roughness: 1.2 });
    applyColors(frame, "var(--line-sketch)");
    svg.appendChild(frame);
  }, [size.w, size.h, v, seed]);

  return (
    <div ref={ref} className="progress" role="progressbar" aria-valuemin={0} aria-valuemax={100}
         aria-valuenow={Math.round(v * 100)} aria-label={label}>
      <svg ref={svgRef} width={size.w} height={size.h} aria-hidden="true" />
    </div>
  );
}

export function AssetImage({ id, alt = "", className }: { id: string; alt?: string; className?: string }) {
  const url = useAssetUrl(id);
  return <img src={url} alt={alt} className={`asset ${className ?? ""}`} draggable={false} />;
}

export function EmptyState({ asset, title, text, action }: { asset: string; title: string; text: string; action?: ReactNode }) {
  return (
    <div className="empty">
      <AssetImage id={asset} className="empty__art" />
      <h2 className="empty__title">{title}</h2>
      <p className="empty__text">{text}</p>
      {action}
    </div>
  );
}

export function Dialog({ open, onClose, title, children }: { open: boolean; onClose: () => void; title: string; children: ReactNode }) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const d = ref.current;
    if (!d) return;
    if (open && !d.open) d.showModal();
    if (!open && d.open) d.close();
  }, [open]);
  return (
    <dialog ref={ref} className="dialog" onClose={onClose} onCancel={onClose}>
      <Sketch className="dialog__body" radius={24}>
        <h2 className="dialog__title">{title}</h2>
        {children}
      </Sketch>
    </dialog>
  );
}

export function ErrorNote({ error }: { error: unknown }) {
  if (!error) return null;
  const msg = error instanceof Error ? error.message : String(error);
  return <p className="error-note" role="alert">{msg}</p>;
}
