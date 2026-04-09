import "./globals.css";

export const metadata = {
  title: "AI Image Style Matcher",
  description: "Extract the mood and style of an image and apply it to another using AI.",
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
      </body>
    </html>
  );
}
