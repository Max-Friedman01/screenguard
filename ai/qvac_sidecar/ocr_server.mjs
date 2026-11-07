// Persistent QVAC OCR helper: loads the model ONCE, then OCRs one image per request.
//
// Protocol (one JSON object per line):
//   stdin : {"id": 1, "path": "C:\\...\\frame.png"}
//   stdout: {"id": 1, "status": "checked", "blocks": [{text, bbox, confidence}, ...]}
//        or {"id": 1, "status": "error", "error": "..."}
//   The first stdout line is {"status": "ready"} once the model is loaded.
// All logging goes to stderr. Closing stdin shuts the helper down cleanly.
import readline from 'node:readline';
import { close, loadModel, ocr, OCR_LATIN, unloadModel } from '@qvac/sdk';

function send(obj) {
  process.stdout.write(JSON.stringify(obj) + '\n');
}

let modelId;

async function shutdown(code) {
  if (modelId !== undefined) {
    try { await unloadModel({ modelId, clearStorage: false }); } catch (e) { console.error('unload failed:', e); }
  }
  try { await close(); } catch (e) { console.error('close failed:', e); }
  process.exit(code);
}

// GPU by default: 'vulkan' runs on NVIDIA/AMD/Intel GPUs on Windows and Linux.
// Override with SCREENGUARD_OCR_DEVICE=cpu if needed.
const device = process.env.SCREENGUARD_OCR_DEVICE || 'vulkan';

function ocrConfig(backendDevice) {
  return {
    langList: ['en'],
    magRatio: 1.0,              // screen text is already crisp; 1.5 meant 2.25x more pixels
    // no defaultRotationAngles: screen text is never rotated, so skip the extra passes
    contrastRetry: false,
    lowConfidenceThreshold: 0.5,
    recognizerBatchSize: 1,
    backendDevice
  };
}

try {
  console.error(`Loading local QVAC OCR model (once) on ${device}...`);
  try {
    modelId = await loadModel({ modelSrc: OCR_LATIN, modelConfig: ocrConfig(device) });
  } catch (error) {
    if (device === 'cpu') throw error;
    console.error(`GPU load failed (${error && error.message ? error.message : error}); falling back to CPU`);
    modelId = await loadModel({ modelSrc: OCR_LATIN, modelConfig: ocrConfig('cpu') });
  }
  console.error(`QVAC OCR model loaded: ${modelId}`);
  send({ status: 'ready' });
} catch (error) {
  console.error(error instanceof Error ? error.stack : error);
  send({ status: 'error', error: String(error && error.message ? error.message : error) });
  await shutdown(1);
}

const rl = readline.createInterface({ input: process.stdin, crlfDelay: Infinity });
for await (const line of rl) {
  if (!line.trim()) continue;
  let id = null;
  try {
    const req = JSON.parse(line);
    id = req.id ?? null;
    const { blocks } = ocr({ modelId, image: req.path, options: { paragraph: false } });
    const result = await blocks;
    send({
      id,
      status: 'checked',
      blocks: result.map((b) => ({ text: b.text, bbox: b.bbox ?? null, confidence: b.confidence ?? null }))
    });
  } catch (error) {
    console.error(error instanceof Error ? error.stack : error);
    send({ id, status: 'error', error: String(error && error.message ? error.message : error) });
  }
}
await shutdown(0);
