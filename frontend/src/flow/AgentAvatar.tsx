import type { NodeStatus } from "./status";

/**
 * Avatar minimalista do agente: "cabeça" geométrica com expressão que reflete o status.
 * idle = sereno · processing = concentrado (olhar varrendo) · completed = satisfeito
 * warning = preocupado · error = contrariado.
 */
export function AgentAvatar({ status, size = 24 }: { status: NodeStatus; size?: number }) {
  return (
    <svg
      className={`agent-avatar avatar-${status}`}
      width={size}
      height={size}
      viewBox="0 0 24 24"
      aria-hidden="true"
    >
      <rect className="avatar-head" x="1" y="1" width="22" height="22" rx="7" />
      <g key={status} className="avatar-face">
        <Face status={status} />
      </g>
    </svg>
  );
}

function Face({ status }: { status: NodeStatus }) {
  switch (status) {
    case "processing":
      return (
        <>
          <g className="avatar-eyes-scan">
            <circle cx="8.5" cy="10.5" r="1.6" className="fill" />
            <circle cx="15.5" cy="10.5" r="1.6" className="fill" />
          </g>
          <path d="M10 16.2h4" />
        </>
      );
    case "completed":
      return (
        <>
          <path d="M6.8 11.2q1.7-2 3.4 0" />
          <path d="M13.8 11.2q1.7-2 3.4 0" />
          <path d="M8.8 15q3.2 2.6 6.4 0" />
        </>
      );
    case "warning":
      return (
        <>
          <path d="M6.9 8.6l3-.9" />
          <path d="M17.1 8.6l-3-.9" />
          <circle cx="8.5" cy="11.3" r="1.3" className="fill" />
          <circle cx="15.5" cy="11.3" r="1.3" className="fill" />
          <path d="M9 16.4q1.5-1 3 0t3 0" />
        </>
      );
    case "error":
      return (
        <>
          <path d="M6.9 7.6l3 .9" />
          <path d="M17.1 7.6l-3 .9" />
          <circle cx="8.5" cy="11.5" r="1.3" className="fill" />
          <circle cx="15.5" cy="11.5" r="1.3" className="fill" />
          <path d="M9 17q3-2.4 6 0" />
        </>
      );
    default:
      return (
        <>
          <path d="M7.2 11h2.6" />
          <path d="M14.2 11h2.6" />
          <path d="M10.2 15.6h3.6" />
        </>
      );
  }
}
