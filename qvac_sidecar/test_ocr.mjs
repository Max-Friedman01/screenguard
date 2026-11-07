import { close, loadModel, ocr, OCR_LATIN, unloadModel } from '@qvac/sdk';

const process = globalThis.process ??
  (await import('bare-process')).default;

const imagePath = process.argv[2];

if (!imagePath) {
  console.error('Usage: node qvac_sidecar/test_ocr.mjs <image-path>');
  process.exitCode = 2;
} else {
  let modelId;

  try {
    console.error('Loading local QVAC OCR model...');
    modelId = await loadModel({
      modelSrc: OCR_LATIN,
      modelConfig: {
        langList: ['en'],
        magRatio: 1.5,
        defaultRotationAngles: [90, 180, 270],
        contrastRetry: false,
        lowConfidenceThreshold: 0.5,
        recognizerBatchSize: 1
      }
    });

    console.error(`QVAC OCR model loaded: ${modelId}`);
    const { blocks } = ocr({
      modelId,
      image: imagePath,
      options: { paragraph: false }
    });
    const result = await blocks;

    process.stdout.write(JSON.stringify({
      status: 'checked',
      blocks: result.map((block) => ({
        text: block.text,
        bbox: block.bbox ?? null,
        confidence: block.confidence ?? null
      }))
    }));
  } catch (error) {
    console.error(error instanceof Error ? error.stack : error);
    process.exitCode = 1;
  } finally {
    if (modelId !== undefined) {
      try {
        await unloadModel({ modelId, clearStorage: false });
      } catch (error) {
        console.error('Failed to unload QVAC OCR model:', error);
        process.exitCode = 1;
      }
    }

    try {
      await close();
    } catch (error) {
      console.error('Failed to close QVAC:', error);
      process.exitCode = 1;
    }
  }
}
