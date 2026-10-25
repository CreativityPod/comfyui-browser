export type FolderSort = 'recent' | 'name';

export interface FolderNode {
  name: string;
  path: string;
  media_count: number;
  modified_at: number;
  created_at: number;
  children: Array<FolderNode>;
  truncated: boolean;
}

const collator = new Intl.Collator(undefined, { numeric: true, sensitivity: 'base' });

export function sortFolders(folders: Array<FolderNode>, mode: FolderSort) {
  const sorted = [...folders];
  if (mode === 'name') {
    sorted.sort((a, b) => collator.compare(a.name, b.name));
  } else {
    sorted.sort((a, b) => b.modified_at - a.modified_at);
  }
  return sorted;
}

export async function fetchFolderTree(comfyUrl: string, folderType: string) {
  const res = await fetch(`${comfyUrl}/browser/files/tree?folder_type=${folderType}`);
  if (!res.ok) {
    throw new Error(`folder tree request failed: ${res.status}`);
  }
  const ret = await res.json();
  return ret.tree as FolderNode;
}

export function findFolder(root: FolderNode | null, folderPath: string): FolderNode | null {
  if (!root) {
    return null;
  }
  if (root.path === folderPath) {
    return root;
  }
  for (const child of root.children) {
    if (folderPath === child.path || folderPath.startsWith(child.path + '/')) {
      return findFolder(child, folderPath);
    }
  }
  return null;
}

// '' for the root, then every parent path down to (but not including) folderPath.
export function ancestorPaths(folderPath: string) {
  const parts = folderPath ? folderPath.split('/') : [];
  const paths = [''];
  for (let i = 1; i < parts.length; i++) {
    paths.push(parts.slice(0, i).join('/'));
  }
  return paths;
}

// Folders whose name matches the query, plus their ancestors so they stay reachable.
export function matchingPaths(root: FolderNode, query: string) {
  const q = query.toLowerCase();
  const result = new Set<string>();

  function walk(node: FolderNode): boolean {
    let keep = node.path !== '' && node.name.toLowerCase().includes(q);
    for (const child of node.children) {
      if (walk(child)) {
        keep = true;
      }
    }
    if (keep) {
      result.add(node.path);
    }
    return keep;
  }

  walk(root);
  return result;
}


export interface TreeRow {
  node: FolderNode;
  depth: number;
  open: boolean;
  parent: string | null;
}

// The rows the tree shows, top to bottom, which is also the order arrow keys move in.
export function flattenTree(
  root: FolderNode,
  expanded: Set<string>,
  mode: FolderSort,
  visible: Set<string> | null,
) {
  const rows: Array<TreeRow> = [];

  function walk(node: FolderNode, depth: number, parent: string | null) {
    const open = node.children.length > 0 && (visible ? true : expanded.has(node.path));
    rows.push({ node, depth, open, parent });
    if (!open) {
      return;
    }
    for (const child of sortFolders(node.children, mode)) {
      if (!visible || visible.has(child.path)) {
        walk(child, depth + 1, node.path);
      }
    }
  }

  walk(root, 0, null);
  return rows;
}

// Points a saved path at the folder's new location after a rename.
export function movePath(p: string, from: string, to: string) {
  if (p === from) {
    return to;
  }
  if (p.startsWith(from + '/')) {
    return to + p.slice(from.length);
  }
  return p;
}
