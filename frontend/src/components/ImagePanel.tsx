import { useRef, useState } from 'react'
import { moderateImage, type ImageModerationResult } from '../api'

const LABEL_STYLES: Record<string, string> = {
  safe: 'bg-green-950 text-green-400 border-green-800',
  suspicious: 'bg-yellow-950 text-yellow-400 border-yellow-800',
  violation: 'bg-red-950 text-red-400 border-red-800',
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`
}

export function ImagePanel() {
  const inputRef = useRef<HTMLInputElement>(null)
  const [result, setResult] = useState<ImageModerationResult | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [preview, setPreview] = useState<string | null>(null)

  const handleFile = async (file: File) => {
    setLoading(true)
    setError(null)
    setResult(null)

    // Show preview
    const reader = new FileReader()
    reader.onload = (e) => setPreview(e.target?.result as string)
    reader.readAsDataURL(file)

    try {
      const r = await moderateImage(file)
      setResult(r)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Image moderation failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="rounded-xl border border-zinc-800 bg-zinc-900/50 p-6">
      <h2 className="mb-4 text-lg font-semibold text-zinc-100">Image Moderation</h2>

      {error && (
        <div className="mb-4 rounded-lg border border-red-900 bg-red-950/50 px-4 py-2 text-sm text-red-400">
          ⚠ {error}
        </div>
      )}

      {/* Upload area */}
      <div
        onClick={() => inputRef.current?.click()}
        onDragOver={(e) => e.preventDefault()}
        onDrop={(e) => {
          e.preventDefault()
          const file = e.dataTransfer.files[0]
          if (file) handleFile(file)
        }}
        className="flex cursor-pointer flex-col items-center justify-center rounded-lg border-2 border-dashed border-zinc-700 p-8 transition hover:border-zinc-500"
      >
        {preview ? (
          <img
            src={preview}
            alt="Preview"
            className="mb-3 max-h-32 rounded-lg object-contain"
          />
        ) : (
          <div className="mb-2 text-3xl">🖼️</div>
        )}
        <p className="text-sm text-zinc-500">
          {loading ? 'Analyzing…' : 'Drop image or click to upload'}
        </p>
        <input
          ref={inputRef}
          type="file"
          accept="image/*"
          className="hidden"
          onChange={(e) => {
            const file = e.target.files?.[0]
            if (file) handleFile(file)
          }}
        />
      </div>

      {/* Result */}
      {result && (
        <div className="mt-4 space-y-3">
          <div className="flex items-center gap-3">
            <span
              className={`rounded-full border px-3 py-1 text-sm font-medium ${
                LABEL_STYLES[result.label] ?? LABEL_STYLES.safe
              }`}
            >
              {result.label.toUpperCase()}
            </span>
            <span className="text-sm text-zinc-400">
              {formatBytes(result.file_size_bytes)}
            </span>
            <span className="text-xs text-zinc-600">
              {result.processing_time_ms.toFixed(2)}ms
            </span>
          </div>

          <div>
            <span className="text-xs text-zinc-600">Confidence</span>
            <div className="mt-1 h-2 overflow-hidden rounded-full bg-zinc-800">
              <div
                className={`h-full transition-all ${
                  result.label === 'safe'
                    ? 'bg-green-500'
                    : result.label === 'suspicious'
                      ? 'bg-yellow-500'
                      : 'bg-red-500'
                }`}
                style={{ width: `${result.confidence * 100}%` }}
              />
            </div>
            <span className="mt-1 block text-sm text-zinc-400">
              {(result.confidence * 100).toFixed(1)}%
            </span>
          </div>

          {result.detected_issues.length > 0 && (
            <div>
              <h3 className="mb-1 text-xs font-medium text-zinc-600">Detected Issues</h3>
              <ul className="space-y-1">
                {result.detected_issues.map((issue, i) => (
                  <li key={i} className="text-xs text-yellow-400">
                    • {issue}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
