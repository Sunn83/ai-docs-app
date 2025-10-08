import './globals.css'

export const metadata = { title: 'AI Docs Chat' }

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="el">
      <body className="bg-gray-100 text-gray-900">{children}</body>
    </html>
  )
}
