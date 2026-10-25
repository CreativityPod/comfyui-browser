# ChangeLog

## v1.9.0 - 2026-10-25

### Image viewer

- Clicking a thumbnail in Outputs or Saves now opens an in-app viewer instead of the raw file (Ctrl/Cmd-click still opens the file in a new tab)
- Prev/next arrows on both sides of the image browse images and videos in the current folder, in grid order and respecting the search filter
- Keyboard: ←/→ to browse, I to toggle the info panel, Esc to close; clicking the backdrop no longer closes the viewer
- Info panel shows file size and date, plus the model, LoRAs, positive/negative prompts, seed, steps, CFG, sampler, scheduler and denoise read from ComfyUI metadata in PNG/WebP files; A1111 parameters are shown as plain text
- Prompt detection follows the sampler inputs back to the text encoder through switch, preview, wildcard, string concat, guider and LLM (TextGenerate) nodes, and leaves Negative empty when it is zeroed out
- Resolution, megapixels and named aspect ratio rows (e.g. `≈ 2:3 (Portrait Photo)`); odd shapes show as a decimal ratio such as `2.07:1 (Landscape)`
- Load workflow into ComfyUI, copy it, or download it as .json; Copy buttons show "✓ Copied" after a successful copy
- Collapsible "Workflow JSON (editor graph)" and "API prompt JSON (what was executed)" sections
- New `GET /browser/files/metadata` endpoint (video metadata is not read yet)

### Outputs folder tree

- The Outputs tab is split into a folder tree on the left and the selected folder's thumbnails on the right
- Reopens the last viewed folder; "Recently viewed" keeps the last 6 folders
- Pin folders to a "Pinned" section at the top of the tree; Pinned and Recently viewed are collapsible
- "Find folder" filters the whole tree by name, including nested folders
- Sort folders by most recent activity or by name; each folder shows its image/video count
- Rename folders in place (pencil icon, Rename on a subfolder tile, or F2); pins and recent folders follow the new name. New `POST /browser/files/rename` endpoint that refuses name clashes and names containing `/`
- Keyboard navigation in the tree: ↑/↓ move, →/← expand or collapse (or go to parent), Home/End, F2 to rename, Delete or Cmd/Ctrl+Backspace to delete
- Main panel has a clickable breadcrumb path, filename filter, sort (newest, oldest, name) and S/M/L thumbnail sizes; subfolders show as compact tiles
- Resizable and hideable side panel; layout settings are remembered
- New `GET /browser/files/tree` endpoint
- Removed Save from folders (it copied the whole folder into Saves); Save is still available on images and workflows

## v1.8.1 - 2024-03-22

- Update xyz_plot to support score mode

## v1.8.0 - 2024-03-19

- Update xyz_plot to support Z axis

## v1.7.0 - 2024-01-14

- Add xyz_plot and select_inputs nodes

## v1.6.1 - 2023-12-31

- Fix some bugs about CollectionsTab

## v1.6.0 - 2023-12-30

- Add i18n support and zh-CN language

## v1.5.3 - 2023-12-23

- Merge the same name JSON and media file in the same directory

## v1.5.2 - 2023-12-20

- Support resize the modal
- Remember the last Tab select

## v1.5.1 - 2023-12-20

- Add Side/Center toggle
- Update styles for responsive

## v1.5.0 - 2023-12-15

- Update styles
- Add recommend sources

## v1.4.0 - 2023-12-13

- Add 'Sources' tab to subscribe external workflow git repository

## v1.3.0 - 2023-12-11

- Support subfolder for output and collection

## v1.2.0 - 2023-12-10

- Can collect current graph to Collections as a workflow.json

## v1.1.0 - 2023-12-09

- Can sync collections to remote git repository

## v1.0.0 - 2023-12-08

- Add image/video/workflow Browser for output folder
- Add Collections for image/video/workflow
