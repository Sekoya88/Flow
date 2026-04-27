import { ImageResponse } from "next/og";

export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

export default function OgImage() {
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          backgroundColor: "#0d0d0d",
          gap: 32,
        }}
      >
        <svg
          width="240"
          height="240"
          viewBox="0 0 64 64"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
        >
          <path
            d="M 8 32 C 8 12, 28 12, 32 32 C 36 52, 56 52, 56 32 C 56 12, 36 12, 32 32 C 28 52, 8 52, 8 32 Z"
            stroke="white"
            strokeWidth="3"
            strokeLinecap="round"
            fill="none"
          />
        </svg>
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            gap: 12,
          }}
        >
          <span
            style={{
              color: "white",
              fontSize: 72,
              fontWeight: 600,
              letterSpacing: "-2px",
              lineHeight: 1,
            }}
          >
            Flow
          </span>
          <span
            style={{
              color: "#888888",
              fontSize: 28,
              fontWeight: 400,
            }}
          >
            Agent platform · workspace
          </span>
        </div>
      </div>
    ),
    { ...size }
  );
}
