import { useEffect, useMemo, useState } from "react";
import {
  ChevronDown,
  ChevronRight,
  ChevronsDownUp,
  ChevronsUpDown,
  Folder,
  FolderOpen,
  Search,
  X,
} from "lucide-react";
import Button from "../common/Button";
import { buildTree, getAllFolderPaths, getParentFolders } from "../../utils/fileTree";
import type { TreeNode } from "../../utils/fileTree";
import { getExtension } from "../../utils/language";

type ExplorerPanelProps = {
  projectName: string;
  paths: string[]; // every file path in the project
  activePath: string;
  onSelect: (path: string) => void;
};

// ---------- one file row ----------

type FileButtonProps = {
  path: string;
  label: string;
  depth: number;
  active: boolean;
  onSelect: (path: string) => void;
};

function FileButton({ path, label, depth, active, onSelect }: FileButtonProps) {
  return (
    <button
      type="button"
      title={path}
      aria-current={active ? "true" : undefined}
      onClick={() => onSelect(path)}
      style={{ paddingLeft: `${depth * 12 + 8}px` }}
      className={`flex w-full items-center gap-2 rounded py-1 pr-2 text-left transition ${
        active ? "bg-saffron/15 text-saffron" : "text-muted hover:bg-raised hover:text-main"
      }`}
    >
      <span className="min-w-7 shrink-0 rounded border border-line px-1 text-center font-mono text-[10px] leading-4 text-gold">
        {getExtension(path)}
      </span>
      <span className="truncate font-mono text-xs">{label}</span>
    </button>
  );
}

// ---------- the tree (calls itself for sub-folders) ----------

type TreeProps = {
  nodes: TreeNode[];
  depth: number;
  expanded: Set<string>;
  activePath: string;
  onToggle: (path: string) => void;
  onSelect: (path: string) => void;
};

function Tree({ nodes, depth, expanded, activePath, onToggle, onSelect }: TreeProps) {
  return (
    <ul>
      {nodes.map((node) => {
        if (node.type === "file") {
          return (
            <li key={node.path}>
              <FileButton
                path={node.path}
                label={node.name}
                depth={depth}
                active={node.path === activePath}
                onSelect={onSelect}
              />
            </li>
          );
        }

        const open = expanded.has(node.path);
        return (
          <li key={node.path}>
            <button
              type="button"
              aria-expanded={open}
              onClick={() => onToggle(node.path)}
              style={{ paddingLeft: `${depth * 12 + 4}px` }}
              className="flex w-full items-center gap-1.5 rounded py-1 pr-2 text-left text-main transition hover:bg-raised"
            >
              {open ? (
                <ChevronDown size={14} className="shrink-0 text-muted" />
              ) : (
                <ChevronRight size={14} className="shrink-0 text-muted" />
              )}
              {open ? (
                <FolderOpen size={15} className="shrink-0 text-saffron" />
              ) : (
                <Folder size={15} className="shrink-0 text-saffron" />
              )}
              <span className="truncate text-sm">{node.name}</span>
            </button>
            {open && (
              <Tree
                nodes={node.children}
                depth={depth + 1}
                expanded={expanded}
                activePath={activePath}
                onToggle={onToggle}
                onSelect={onSelect}
              />
            )}
          </li>
        );
      })}
    </ul>
  );
}

// ---------- the panel ----------

export default function ExplorerPanel({
  projectName,
  paths,
  activePath,
  onSelect,
}: ExplorerPanelProps) {
  const tree = useMemo(() => buildTree(paths), [paths]);
  const allFolders = useMemo(() => getAllFolderPaths(tree), [tree]);

  // folders open at start: top-level ones, and the ones holding the active file
  const [expanded, setExpanded] = useState<Set<string>>(() => {
    const open = new Set<string>();
    for (const node of tree) {
      if (node.type === "folder") open.add(node.path);
    }
    for (const folder of getParentFolders(activePath)) open.add(folder);
    return open;
  });
  const [query, setQuery] = useState("");

  // when the active file changes, make sure its folders are open
  useEffect(() => {
    setExpanded((current) => {
      const missing = getParentFolders(activePath).filter((f) => !current.has(f));
      if (missing.length === 0) return current;
      return new Set([...current, ...missing]);
    });
  }, [activePath]);

  function toggle(path: string) {
    setExpanded((current) => {
      const next = new Set(current);
      if (next.has(path)) next.delete(path);
      else next.add(path);
      return next;
    });
  }

  const search = query.trim().toLowerCase();
  const results = search ? paths.filter((p) => p.toLowerCase().includes(search)) : [];

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="flex items-center justify-between gap-1 border-b border-line py-1.5 pl-3 pr-1">
        <div className="min-w-0">
          <p className="truncate text-sm font-medium">{projectName}</p>
          <p className="text-xs text-muted">{paths.length} files</p>
        </div>
        <div className="flex shrink-0">
          <Button
            variant="ghost"
            size="icon"
            title="Expand all"
            aria-label="Expand all folders"
            onClick={() => setExpanded(new Set(allFolders))}
          >
            <ChevronsUpDown size={15} />
          </Button>
          <Button
            variant="ghost"
            size="icon"
            title="Collapse all"
            aria-label="Collapse all folders"
            onClick={() => setExpanded(new Set())}
          >
            <ChevronsDownUp size={15} />
          </Button>
        </div>
      </div>

      {/* search */}
      <div className="border-b border-line p-2">
        <div className="relative">
          <Search
            size={14}
            className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-muted"
          />
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search files"
            aria-label="Search files"
            spellCheck={false}
            className="w-full rounded-md border border-line bg-base py-1.5 pl-8 pr-8 text-sm text-main placeholder:text-muted focus:border-saffron focus:outline-none"
          />
          {query && (
            <button
              type="button"
              aria-label="Clear search"
              onClick={() => setQuery("")}
              className="absolute right-2 top-1/2 -translate-y-1/2 text-muted hover:text-main"
            >
              <X size={14} />
            </button>
          )}
        </div>
      </div>

      <div className="min-h-0 flex-1 overflow-auto p-1">
        {search ? (
          results.length > 0 ? (
            <ul>
              {results.map((path) => (
                <li key={path}>
                  <FileButton
                    path={path}
                    label={path}
                    depth={0}
                    active={path === activePath}
                    onSelect={onSelect}
                  />
                </li>
              ))}
            </ul>
          ) : (
            <p className="p-3 text-sm text-muted">No files match "{query.trim()}".</p>
          )
        ) : (
          <Tree
            nodes={tree}
            depth={0}
            expanded={expanded}
            activePath={activePath}
            onToggle={toggle}
            onSelect={onSelect}
          />
        )}
      </div>
    </div>
  );
}