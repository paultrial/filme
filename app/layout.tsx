import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Filme — your movie shelf",
  description: "Find the right film for tonight.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en">
      <body className="min-h-full flex flex-col">{children}</body>
    </html>
  );
}
