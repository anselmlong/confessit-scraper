const base = {
  width: 14, height: 14, viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor',
  strokeWidth: 2, strokeLinecap: 'round' as const, strokeLinejoin: 'round' as const, 'aria-hidden': true,
  className: 'inline-block align-[-2px] shrink-0',
};

export const HeartIcon = () => (
  <svg {...base}><path d="M19.5 12.6 12 20l-7.5-7.4A4.9 4.9 0 0 1 12 6a4.9 4.9 0 0 1 7.5 6.6z" /></svg>
);
export const ReplyIcon = () => (
  <svg {...base}><path d="M21 12a8 8 0 0 1-11.8 7L4 20l1.1-4.6A8 8 0 1 1 21 12z" /></svg>
);
export const UpIcon = () => (
  <svg {...base}><path d="M7 10v11M15 5.9 14 10h5.8a2 2 0 0 1 2 2.3l-1.4 7A2 2 0 0 1 18.4 21H7V10l4.4-7.4a1.6 1.6 0 0 1 3 .9z" /></svg>
);
export const DownIcon = () => (
  <svg {...base}><path d="M17 14V3M9 18.1l1-4.1H4.2a2 2 0 0 1-2-2.3l1.4-7A2 2 0 0 1 5.6 3H17v11l-4.4 7.4a1.6 1.6 0 0 1-3-.9z" /></svg>
);
