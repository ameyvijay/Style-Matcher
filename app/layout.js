import VersionBadge from "../components/VersionBadge";
import Navigation from "../components/Navigation";
import { BatchProvider } from "../components/BatchContext";
import "./globals.css";

export const viewport = {
  themeColor: "#000000",
  width: "device-width",
  initialScale: 1,
  maximumScale: 1,
  userScalable: false,
};

export const metadata = {
  title: "Style Matcher | Pro Photo Culling",
  description: "AI-powered photo culling engine with RLHF feedback loops.",
  manifest: "/manifest.json",
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
        <BatchProvider>
          <Navigation />
          {children}
          <VersionBadge />
        </BatchProvider>
      </body>
    </html>
  );
}
