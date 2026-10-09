import { useCallback, useRef, useState } from "react";

// File types accepted by the drop zone.
const ALLOWED = [".pdf", ".docx", ".xlsx", ".xlsm", ".png", ".jpg", ".jpeg", ".webp", ".bmp"];

/** Return true when a filename has an accepted extension. */
function isAllowed(name: string): boolean {
  const lower = name.toLowerCase();
  return ALLOWED.some((ext) => lower.endsWith(ext));
}

/** Resolve a dropped folder entry to a File. */
function readFile(entry: FileSystemFileEntry): Promise<File> {
  return new Promise((resolve, reject) => entry.file(resolve, reject));
}

/** Read all entries of a directory, paging until the reader is exhausted. */
function readAllEntries(reader: FileSystemDirectoryReader): Promise<FileSystemEntry[]> {
  return new Promise((resolve, reject) => {
    const out: FileSystemEntry[] = [];
    const next = () =>
      reader.readEntries((batch) => {
        if (!batch.length) resolve(out);
        else {
          out.push(...batch);
          next();
        }
      }, reject);
    next();
  });
}

/** Recursively collect allowed files from a dropped file or directory entry. */
async function traverse(entry: FileSystemEntry, files: File[]): Promise<void> {
  if (entry.isFile) {
    const file = await readFile(entry as FileSystemFileEntry);
    if (isAllowed(file.name)) files.push(file);
  } else if (entry.isDirectory) {
    const entries = await readAllEntries((entry as FileSystemDirectoryEntry).createReader());
    for (const child of entries) await traverse(child, files);
  }
}

/** Props for the DropZone component. */
interface Props {
  onFiles: (files: File[]) => void;
  disabled?: boolean;
}

/** Drag-and-drop / browse area for selecting an ITB folder or files. */
export default function DropZone({ onFiles, disabled }: Props) {
  const [dragging, setDragging] = useState(false);
  const dirInput = useRef<HTMLInputElement>(null);
  const fileInput = useRef<HTMLInputElement>(null);

  /** Handle a drop: walk folder entries (or plain files) and report them up. */
  const handleDrop = useCallback(
    async (e: React.DragEvent) => {
      e.preventDefault();
      setDragging(false);
      if (disabled) return;

      const files: File[] = [];
      const items = e.dataTransfer.items;
      const entries: FileSystemEntry[] = [];
      for (const item of Array.from(items)) {
        const entry = item.webkitGetAsEntry?.();
        if (entry) entries.push(entry);
      }
      if (entries.length) {
        for (const entry of entries) await traverse(entry, files);
      } else {
        for (const f of Array.from(e.dataTransfer.files)) {
          if (isAllowed(f.name)) files.push(f);
        }
      }
      if (files.length) onFiles(files);
    },
    [onFiles, disabled]
  );

  /** Handle the hidden file/folder inputs and filter to allowed types. */
  const handleInput = (e: React.ChangeEvent<HTMLInputElement>) => {
    const list = e.target.files;
    if (!list) return;
    const files = Array.from(list).filter((f) => isAllowed(f.name));
    if (files.length) onFiles(files);
    e.target.value = "";
  };

  return (
    <div
      onDragOver={(e) => {
        e.preventDefault();
        if (!disabled) setDragging(true);
      }}
      onDragLeave={() => setDragging(false)}
      onDrop={handleDrop}
      className={[
        "relative rounded-2xl border border-dashed p-10 text-center transition-all duration-200",
        dragging
          ? "border-amber bg-amber/5"
          : "border-ink-600 bg-ink-900/60 hover:border-ink-600/80",
        disabled ? "pointer-events-none opacity-50" : "cursor-pointer",
      ].join(" ")}
      onClick={() => !disabled && dirInput.current?.click()}
    >
      <input
        ref={dirInput}
        type="file"
        multiple
        // @ts-expect-error non-standard directory attributes, supported in Chromium
        webkitdirectory=""
        directory=""
        className="hidden"
        onChange={handleInput}
      />
      <input
        ref={fileInput}
        type="file"
        multiple
        accept={ALLOWED.join(",")}
        className="hidden"
        onChange={handleInput}
      />

      <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-xl border border-ink-600 bg-ink-800">
        <svg
          width="26"
          height="26"
          viewBox="0 0 24 24"
          fill="none"
          stroke="var(--color-amber)"
          strokeWidth="1.6"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" />
          <path d="M12 11v5" />
          <path d="M9.5 13.5 12 11l2.5 2.5" />
        </svg>
      </div>

      <p className="font-mono text-sm text-paper-50">
        Drop your <span className="text-amber">ITB folder</span> here
      </p>
      <p className="mt-1 font-mono text-xs text-ink-600 text-paper-200/50">
        or click to browse &middot; PDFs and screenshots are read automatically
      </p>

      <div className="mt-5 flex items-center justify-center gap-3">
        <button
          type="button"
          className="rounded-lg bg-amber px-4 py-1.5 font-mono text-xs font-semibold text-space-950 transition hover:bg-amber-light"
          onClick={(e) => {
            e.stopPropagation();
            dirInput.current?.click();
          }}
        >
          SELECT FOLDER
        </button>
        <button
          type="button"
          className="rounded-lg border border-ink-600 px-4 py-1.5 font-mono text-xs text-paper-200 transition hover:border-amber hover:text-amber"
          onClick={(e) => {
            e.stopPropagation();
            fileInput.current?.click();
          }}
        >
          SELECT FILES
        </button>
      </div>
    </div>
  );
}
