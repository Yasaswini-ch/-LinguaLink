// Minimal hand-drawn inline icons (no external icon library dependency).
export const IconPerson = (props) => (
  <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2" {...props}>
    <circle cx="12" cy="8" r="3.5" />
    <path d="M5 20c0-3.5 3-6 7-6s7 2.5 7 6" strokeLinecap="round" />
  </svg>
);

export const IconOrg = (props) => (
  <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2" {...props}>
    <path d="M4 21V7l8-4 8 4v14" strokeLinejoin="round" />
    <path d="M4 21h16M9 21v-5h6v5M9 11h.01M15 11h.01M9 15h.01M15 15h.01" strokeLinecap="round" />
  </svg>
);

export const IconLocation = (props) => (
  <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2" {...props}>
    <path d="M12 21s7-6.5 7-11.5a7 7 0 1 0-14 0C5 14.5 12 21 12 21z" strokeLinejoin="round" />
    <circle cx="12" cy="9.5" r="2.3" />
  </svg>
);

export const IconPipeline = (props) => (
  <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2" {...props}>
    <circle cx="5" cy="6" r="2.2" />
    <circle cx="19" cy="6" r="2.2" />
    <circle cx="12" cy="18" r="2.2" />
    <path d="M6.9 7.2 11 16.2M17.1 7.2 13 16.2M7.2 6h9.6" strokeLinecap="round" />
  </svg>
);

export const IconExternal = (props) => (
  <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="2" {...props}>
    <path d="M14 4h6v6M20 4 11 13M10 5H6a1 1 0 0 0-1 1v12a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1v-4" strokeLinecap="round" strokeLinejoin="round" />
  </svg>
);

export const IconChevron = (props) => (
  <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2" {...props}>
    <path d="M9 6l6 6-6 6" strokeLinecap="round" strokeLinejoin="round" />
  </svg>
);

export const IconGlobe = (props) => (
  <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2" {...props}>
    <circle cx="12" cy="12" r="9" />
    <path d="M3 12h18M12 3c2.5 2.6 4 6 4 9s-1.5 6.4-4 9c-2.5-2.6-4-6-4-9s1.5-6.4 4-9z" />
  </svg>
);

export const IconDoc = (props) => (
  <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2" {...props}>
    <path d="M7 3h7l5 5v13H7z" strokeLinejoin="round" />
    <path d="M14 3v5h5M9 12h6M9 16h6" strokeLinecap="round" />
  </svg>
);

export const IconTrash = (props) => (
  <svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" strokeWidth="2" {...props}>
    <path d="M4 7h16M9 7V4h6v3M6 7l1 13h10l1-13" strokeLinecap="round" strokeLinejoin="round" />
  </svg>
);

export const IconInfo = (props) => (
  <svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" strokeWidth="2" {...props}>
    <circle cx="12" cy="12" r="9" />
    <path d="M12 11v5.5" strokeLinecap="round" />
    <circle cx="12" cy="8" r="0.9" fill="currentColor" stroke="none" />
  </svg>
);

export const IconPlay = (props) => (
  <svg viewBox="0 0 24 24" width="13" height="13" fill="currentColor" {...props}>
    <path d="M6 4l14 8-14 8V4z" />
  </svg>
);
