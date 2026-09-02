import { useEffect, useState } from "react";

function prefersReducedMotion(): boolean {
  if (typeof window === "undefined" || typeof window.matchMedia !== "function") {
    return true;
  }
  return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

export function TypewriterText({
  text,
  active,
}: {
  text: string;
  active: boolean;
}) {
  const reduced = prefersReducedMotion();
  const [shown, setShown] = useState(() => (active && !reduced ? "" : text));

  useEffect(() => {
    if (!active || reduced) {
      setShown(text);
      return;
    }
    setShown("");
    let index = 0;
    const timer = window.setInterval(() => {
      index += 1;
      setShown(text.slice(0, index));
      if (index >= text.length) {
        window.clearInterval(timer);
      }
    }, 16);
    return () => window.clearInterval(timer);
  }, [text, active, reduced]);

  return <span>{shown}</span>;
}
