"use client";

import { ArrowUp } from "@phosphor-icons/react";
import { type ReactNode, useEffect, useRef, useState } from "react";

type Props = {
  placeholder: string;
  disabled?: boolean;
  large?: boolean;
  autoFocus?: boolean;
  /** Shown in the large composer's bottom row, beside the send button. */
  footer?: ReactNode;
  onSend: (text: string) => void;
  onFocusChange?: (focused: boolean) => void;
  onTextChange?: (text: string) => void;
};

/** The one place the student types: the first brief, answers to Jai's questions, refinements. */
export function Composer({
  placeholder,
  disabled = false,
  large = false,
  autoFocus = false,
  footer,
  onSend,
  onFocusChange,
  onTextChange,
}: Props) {
  const [text, setText] = useState("");
  const box = useRef<HTMLTextAreaElement>(null);
  const ready = text.trim().length > 0 && !disabled;

  // focus on load only with a mouse or trackpad, and without scrolling the page; on a phone the
  // keyboard would cover the page before the student has seen it
  useEffect(() => {
    if (autoFocus && window.matchMedia("(pointer: fine)").matches) box.current?.focus({ preventScroll: true });
  }, [autoFocus]);

  // grow with the text, up to a few lines
  useEffect(() => {
    const el = box.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, large ? 180 : 132)}px`;
  }, [text, large]);

  const send = () => {
    if (!ready) return;
    onSend(text.trim());
    setText("");
    onTextChange?.("");
  };

  const button = (
    <button
      type="submit"
      disabled={!ready}
      aria-label="Send"
      className="fj-sunset grid size-10 flex-none place-items-center rounded-xl transition"
    >
      <ArrowUp size={18} weight="bold" />
    </button>
  );

  const field = (
    <textarea
      ref={box}
      value={text}
      rows={large ? 2 : 1}
      maxLength={2000}
      disabled={disabled}
      placeholder={placeholder}
      onChange={(e) => {
        setText(e.target.value);
        onTextChange?.(e.target.value);
        window.dispatchEvent(new Event("fj:typing")); // Jai looks at the box and nods along
      }}
      onFocus={() => {
        onFocusChange?.(true);
        window.dispatchEvent(new Event("fj:typing"));
      }}
      onBlur={() => onFocusChange?.(false)}
      onKeyDown={(e) => {
        if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
          e.preventDefault(); // Enter sends; Shift+Enter breaks the line (and IME composing is left alone)
          send();
        }
      }}
      className={`min-w-0 flex-1 resize-none bg-transparent px-3 py-2 text-fg outline-none placeholder:text-faint disabled:opacity-50 ${
        large ? "text-[17px] leading-relaxed" : "text-[15px]"
      }`}
    />
  );

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        send();
      }}
      className={
        large
          ? "flex flex-col gap-1 rounded-[19px] bg-raised p-2.5"
          : "flex items-end gap-2 rounded-2xl bg-raised p-2 ring-1 ring-line transition focus-within:ring-amber/50"
      }
    >
      {large ? (
        <>
          {field}
          <div className="flex items-end gap-3 pl-1.5">
            <div className="min-w-0 flex-1">{footer}</div>
            {button}
          </div>
        </>
      ) : (
        <>
          {field}
          {button}
        </>
      )}
    </form>
  );
}
