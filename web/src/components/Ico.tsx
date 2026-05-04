// Inline SVG icons. Stroked, currentColor — match the wireframes' minimal feel.
import type { SVGProps } from "react";

type IconName =
  | "send"
  | "plus"
  | "thumbUp"
  | "thumbDown"
  | "copy"
  | "redo"
  | "share"
  | "lock"
  | "chev"
  | "ext"
  | "search"
  | "help";

interface IcoProps extends Omit<SVGProps<SVGSVGElement>, "name"> {
  name: IconName;
  size?: number;
}

const PATHS: Record<IconName, JSX.Element> = {
  send: (
    <path
      d="M3.4 11 20 4.5 13.5 21l-2.8-7.4L3.4 11Z"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinejoin="round"
    />
  ),
  plus: (
    <>
      <path d="M12 5v14" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
      <path d="M5 12h14" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
    </>
  ),
  thumbUp: (
    <path
      d="M7 10v9H4v-9h3Zm2 0 3-7c1.5 0 2.5 1 2.5 2.5V8h4.5A1.5 1.5 0 0 1 20.5 9.5l-1.7 7A2 2 0 0 1 16.9 18H9V10Z"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.4"
      strokeLinejoin="round"
    />
  ),
  thumbDown: (
    <path
      d="M17 14V5h3v9h-3Zm-2 0-3 7c-1.5 0-2.5-1-2.5-2.5V16H5A1.5 1.5 0 0 1 3.5 14.5l1.7-7A2 2 0 0 1 7.1 6H15v8Z"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.4"
      strokeLinejoin="round"
    />
  ),
  copy: (
    <>
      <rect
        x="8"
        y="8"
        width="11"
        height="12"
        rx="1.5"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.4"
      />
      <path
        d="M5 16V5.5A1.5 1.5 0 0 1 6.5 4H15"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.4"
        strokeLinecap="round"
      />
    </>
  ),
  redo: (
    <path
      d="M14 6 18 10l-4 4M18 10H9a5 5 0 0 0-5 5v3"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.4"
      strokeLinecap="round"
      strokeLinejoin="round"
    />
  ),
  share: (
    <path
      d="M14 4h6v6M20 4 11 13M18 14v4a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.4"
      strokeLinecap="round"
      strokeLinejoin="round"
    />
  ),
  lock: (
    <>
      <rect
        x="5"
        y="11"
        width="14"
        height="9"
        rx="1.5"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.4"
      />
      <path
        d="M8 11V8a4 4 0 0 1 8 0v3"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.4"
      />
    </>
  ),
  chev: (
    <path
      d="m6 9 6 6 6-6"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
    />
  ),
  ext: (
    <>
      <path
        d="M14 4h6v6"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.4"
        strokeLinecap="round"
      />
      <path
        d="M20 4 11 13"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.4"
        strokeLinecap="round"
      />
      <path
        d="M18 14v4a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.4"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </>
  ),
  search: (
    <>
      <circle
        cx="11"
        cy="11"
        r="6"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.4"
      />
      <path
        d="m20 20-4.5-4.5"
        stroke="currentColor"
        strokeWidth="1.4"
        strokeLinecap="round"
      />
    </>
  ),
  help: (
    <>
      <circle
        cx="12"
        cy="12"
        r="9"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.4"
      />
      <path
        d="M9.5 9.5a2.5 2.5 0 1 1 3.5 2.3c-.7.3-1 .9-1 1.6V14"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.4"
        strokeLinecap="round"
      />
      <circle cx="12" cy="17" r="0.9" fill="currentColor" />
    </>
  ),
};

export function Ico({ name, size = 16, ...rest }: IcoProps) {
  return (
    <svg
      viewBox="0 0 24 24"
      width={size}
      height={size}
      aria-hidden="true"
      focusable="false"
      {...rest}
    >
      {PATHS[name]}
    </svg>
  );
}
