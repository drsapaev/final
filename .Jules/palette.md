## 2025-02-22 - [FileUpload Accessibility]
**Learning:** `react-dropzone` exposes an `isFocused` state that is critical for visual feedback when using keyboard navigation, often overlooked in favor of just `isDragActive`.
**Action:** Always destructure `isFocused` when using `useDropzone` and add visual indicators (like border color) for it.
