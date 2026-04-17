import VersionBadge from "../components/VersionBadge";
import "./globals.css";

export const metadata = {
  title: "Style Matcher | Pro Photo Culling",
  description: "AI-powered photo culling engine with RLHF feedback loops.",
  manifest: "/manifest.json",
  themeColor: "#000000",
  viewport: {
    width: "device-width",
    initialScale: 1,
    maximumScale: 1,
    userScalable: false,
  },
  icons: {
    icon: "/icon-512x512.png",
    apple: "/icon-512x512.png",
  },
  appleWebApp: {
    capable: true,
    statusBarStyle: "black-translucent",
    title: "Style Matcher",
  },
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>
        <div className="bg-blobs">
          <div className="blob blob-1"></div>
          <div className="blob blob-2"></div>
        </div>
        {children}
        <VersionBadge />
      </body>
    </html>
  );
}
