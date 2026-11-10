## Read

Read a text file, or load an image for vision models.

- Text: returns the full content with line numbers. A single read is capped at 10MB; for larger files pass `offset` and `limit` together (1-based, inclusive range). Passing only one of them is an error.
- Images: png/jpg/jpeg/webp/gif/bmp up to 15MB, detected by extension or file magic. The image is attached to the conversation for visual inspection.
- Load all needed images in one batch of tool calls; images from earlier turns may be compacted later.
- Use `Grep` to find content and `Glob` to find files; do not read whole trees blindly.
- PDF/DOCX are not supported.
