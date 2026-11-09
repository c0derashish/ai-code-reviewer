export type FileNode = { type: "file"; name: string; path: string };
export type FolderNode = {
  type: "folder";
  name: string;
  path: string;
  children: TreeNode[];
};
export type TreeNode = FileNode | FolderNode;

// folders first, then files, each A to Z
function sortNodes(nodes: TreeNode[]) {
  nodes.sort((a, b) => {
    if (a.type !== b.type) return a.type === "folder" ? -1 : 1;
    return a.name.localeCompare(b.name);
  });
  for (const node of nodes) {
    if (node.type === "folder") sortNodes(node.children);
  }
}

export function buildTree(paths: string[]): TreeNode[] {
  const root: TreeNode[] = [];
  const folders = new Map<string, FolderNode>();

  for (const path of paths) {
    const parts = path.split("/");
    let siblings = root;
    let current = "";

    // walk through the folders, make the missing ones
    for (let i = 0; i < parts.length - 1; i++) {
      current = current ? `${current}/${parts[i]}` : parts[i];
      let folder = folders.get(current);
      if (!folder) {
        folder = { type: "folder", name: parts[i], path: current, children: [] };
        folders.set(current, folder);
        siblings.push(folder);
      }
      siblings = folder.children;
    }

    siblings.push({ type: "file", name: parts[parts.length - 1], path });
  }

  sortNodes(root);
  return root;
}

// "src/utils/a.py" -> ["src", "src/utils"]
export function getParentFolders(path: string): string[] {
  const parts = path.split("/").slice(0, -1);
  const result: string[] = [];
  let current = "";
  for (const part of parts) {
    current = current ? `${current}/${part}` : part;
    result.push(current);
  }
  return result;
}

export function getAllFolderPaths(nodes: TreeNode[]): string[] {
  const result: string[] = [];
  for (const node of nodes) {
    if (node.type === "folder") {
      result.push(node.path);
      result.push(...getAllFolderPaths(node.children));
    }
  }
  return result;
}