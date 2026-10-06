"""Windows offline OCR. No image or account data is sent to a service."""
import asyncio
from pathlib import Path


async def recognize(path, language=None):
    from winrt.windows.storage import StorageFile, FileAccessMode
    from winrt.windows.graphics.imaging import BitmapDecoder
    from winrt.windows.media.ocr import OcrEngine
    if language:
        from winrt.windows.globalization import Language
        engine = OcrEngine.try_create_from_language(Language(language))
    else:
        engine = OcrEngine.try_create_from_user_profile_languages()
    if engine is None:
        requested = language or '当前用户语言'
        raise RuntimeError(f'Windows OCR 不支持所请求的语言：{requested}，请检查对应语言识别组件')
    file = await StorageFile.get_file_from_path_async(str(Path(path).resolve()))
    stream = await file.open_async(FileAccessMode.READ)
    try:
        decoder = await BitmapDecoder.create_async(stream)
        bitmap = await decoder.get_software_bitmap_async()
        try:
            result = await engine.recognize_async(bitmap)
            return [{'text': word.text, 'rect': [word.bounding_rect.x, word.bounding_rect.y,
                     word.bounding_rect.width, word.bounding_rect.height]}
                    for line in result.lines for word in line.words]
        finally:
            bitmap.close()
    finally:
        stream.close()


async def recognize_chart(path, language=None):
    from PIL import Image, ImageOps
    from tempfile import TemporaryDirectory
    words = await recognize(path, language)
    with Image.open(path) as source:
        if source.width < 1000 or source.height < 500:
            return words
        height = min(300, source.height // 3)
        enhanced = []
        with TemporaryDirectory(prefix='stocklink-text-') as directory:
            for left in range(0, source.width, 1000):
                crop_left, crop_right = max(0, left - 40), min(source.width, left + 1040)
                tile = source.crop((crop_left, 0, crop_right, height))
                tile = tile.resize((tile.width * 2, tile.height * 2), Image.Resampling.LANCZOS)
                target = Path(directory) / 'tile.png'
                tile.save(target)
                for word in await recognize(target, language):
                    x, y, width, h = word['rect']
                    rect = [x / 2 + crop_left, y / 2, width / 2, h / 2]
                    if left <= rect[0] + rect[2] / 2 < min(source.width, left + 1000):
                        enhanced.append({'text': word['text'], 'rect': rect})
            # Small gray period labels need a tight, high-contrast crop.
            # Accept replacement only when the entire ordered toolbar is read.
            for anchor in list(enhanced):
                if anchor['text'] != '\u5468':
                    continue
                x, y, width, h = anchor['rect']
                bounds = (max(0, int(x - 3 * h)), max(0, int(y - h)),
                          min(source.width, int(x + 7 * h)), min(height, int(y + 2 * h)))
                tile = ImageOps.invert(source.crop(bounds).convert('L'))
                tile = tile.resize((tile.width * 4, tile.height * 4), Image.Resampling.LANCZOS)
                target = Path(directory) / 'period.png'
                tile.save(target)
                labels = []
                for word in await recognize(target, language):
                    if word['text'] in ('\u65e5', '\u5468', '\u6708', '\u5b63', '\u5e74'):
                        a, b, w, hh = word['rect']
                        labels.append({'text': word['text'],
                                       'rect': [bounds[0] + a / 4, bounds[1] + b / 4, w / 4, hh / 4]})
                labels.sort(key=lambda word: word['rect'][0])
                if [word['text'] for word in labels] == ['\u65e5', '\u5468', '\u6708', '\u5b63', '\u5e74']:
                    enhanced = [word for word in enhanced if not (
                        bounds[0] <= word['rect'][0] < bounds[2]
                        and bounds[1] <= word['rect'][1] < bounds[3])]
                    enhanced.extend(labels)
        return [word for word in words if word['rect'][1] >= height] + enhanced


def main(argv=None):
    import json
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('image')
    parser.add_argument('--output', default='live-ocr.json')
    parser.add_argument('--language')
    args = parser.parse_args(argv)
    result = asyncio.run(recognize_chart(args.image, args.language))
    Path(args.output).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print('Words:', len(result))


if __name__ == '__main__':
    main()
