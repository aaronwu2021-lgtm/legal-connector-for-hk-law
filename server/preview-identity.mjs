import { createHash } from 'node:crypto';
import { realpathSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

// Identifies this checkout without returning its local filesystem path.
export const previewId = createHash('sha256')
  .update(realpathSync(fileURLToPath(new URL('.', import.meta.url))))
  .digest('hex');
