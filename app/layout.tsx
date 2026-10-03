import type { Metadata } from "next";
import type { ReactNode } from "react";
import "./globals.css";

export const metadata: Metadata = {
  title: "Odal BIBI | 자격증 준비 대시보드",
  description: "추천, 시험 일정, 프로필, 채팅을 한곳에서 정리하는 자격증 준비 대시보드.",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="ko">
      <body>{children}</body>
    </html>
  );
}
