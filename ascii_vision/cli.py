import argparse
import glob as glob_module
import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Optional

from PIL import Image, ImageOps, ExifTags

ASCII_CHARSET = "@%#*+=-:. "
BLOCK_CHARSET = " ░▒▓█"
EXTENDED_ASCII = "@$%B#8&WM*oahkbdpqwmZO0QLCJUYXzcvunxrjft/\\|()1{}[]?-_+~<>i!lI;:,\"^`'. "

NAMED_COLORS: dict[str, tuple[int, int, int]] = {
    "W": (255, 255, 255),
    "K": (0, 0, 0),
    "R": (220, 50, 50),
    "G": (50, 180, 50),
    "B": (50, 80, 220),
    "Y": (230, 210, 50),
    "C": (50, 200, 210),
    "M": (200, 50, 180),
    "O": (240, 140, 30),
    "P": (150, 50, 200),
    "L": (130, 210, 130),
    "D": (100, 100, 100),
    "S": (180, 180, 180),
    "N": (100, 60, 20),
    "I": (240, 160, 160),
    "T": (100, 180, 220),
}

COLOR_NAMES_RU = {
    "W": "белый", "K": "чёрный", "R": "красный", "G": "зелёный",
    "B": "синий", "Y": "жёлтый", "C": "голубой", "M": "пурпурный",
    "O": "оранжевый", "P": "фиолетовый", "L": "салатовый", "D": "тёмно-серый",
    "S": "серый", "N": "коричневый", "I": "розовый", "T": "бирюзовый",
}

_ocr_cache: dict[tuple, Optional[list[dict]]] = {}
_pytesseract_available: Optional[bool] = None


def _check_pytesseract() -> bool:
    global _pytesseract_available
    if _pytesseract_available is None:
        try:
            import pytesseract  # noqa: F401
            _pytesseract_available = True
        except ImportError:
            _pytesseract_available = False
    return _pytesseract_available


def _warn_ocr(msg: str) -> None:
    print(f"[ascii-vision] {msg}", file=sys.stderr)


def _otsu_threshold(pixels: list[int]) -> int:
    hist = [0] * 256
    for p in pixels:
        hist[p] += 1
    total = len(pixels)
    if total == 0:
        return 128
    sum_all = sum(i * hist[i] for i in range(256))
    sum_b = 0
    w_b = 0
    max_var = 0.0
    threshold = 128
    for t in range(256):
        w_b += hist[t]
        if w_b == 0:
            continue
        w_f = total - w_b
        if w_f == 0:
            break
        sum_b += t * hist[t]
        m_b = sum_b / w_b
        m_f = (sum_all - sum_b) / w_f
        var = w_b * w_f * (m_b - m_f) ** 2
        if var > max_var:
            max_var = var
            threshold = t
    return threshold


def _make_charset(base: str, levels: int) -> str:
    if levels <= len(base):
        return base[:levels]
    result = []
    step = (len(base) - 1) / (levels - 1)
    for i in range(levels):
        idx = min(int(round(i * step)), len(base) - 1)
        result.append(base[idx])
    return "".join(result)


def _effective_width(requested: Optional[int], orig_w: int, max_w: Optional[int]) -> int:
    w = requested if requested is not None else orig_w
    if max_w is not None and w > max_w:
        w = max_w
    return w


def _get_exif_info(img: Image.Image) -> dict[str, str]:
    try:
        exif = img.getexif()
    except Exception:
        return {}
    if not exif:
        return {}
    info: dict[str, str] = {}
    for tag_id, value in exif.items():
        tag_name = ExifTags.TAGS.get(tag_id, str(tag_id))
        if tag_name in ("MakerNote", "UserComment", "PrintImageMatching"):
            continue
        if isinstance(value, bytes):
            try:
                value = value.decode("utf-8", errors="replace")
            except Exception:
                value = str(value)
        info[tag_name] = str(value)
    return info


def _format_exif(info: dict[str, str]) -> str:
    if not info:
        return ""
    lines = ["## EXIF Metadata", "```text"]
    for k, v in info.items():
        lines.append(f"  {k}: {v}")
    lines.append("```")
    return "\n".join(lines)


def _handle_pdf(pdf_path: Path) -> list[Path]:
    try:
        from pdf2image import convert_from_path
    except ImportError:
        raise RuntimeError(
            "PDF support requires pdf2image. Install with: pip install pdf2image"
        )
    images = convert_from_path(str(pdf_path))
    result = []
    for i, img in enumerate(images):
        temp = pdf_path.parent / f"{pdf_path.stem}_page_{i + 1}.png"
        img.save(str(temp))
        result.append(temp)
    return result


def _parse_crop(value: str) -> tuple[int, int, int, int]:
    parts = value.split(",")
    if len(parts) != 4:
        raise argparse.ArgumentTypeError(
            "--crop must be X,Y,W,H (e.g. 0,0,500,400)"
        )
    return tuple(int(p.strip()) for p in parts)  # type: ignore[return-value]


def _read_stdin() -> Path:
    data = sys.stdin.buffer.read()
    if not data:
        raise RuntimeError("No data on stdin")
    if data[:4] == b"\x89PNG":
        suffix = ".png"
    elif data[:2] == b"\xff\xd8":
        suffix = ".jpg"
    elif data[:4] == b"RIFF":
        suffix = ".webp"
    else:
        suffix = ".png"
    fd, path = tempfile.mkstemp(suffix=suffix)
    with os.fdopen(fd, "wb") as f:
        f.write(data)
    return Path(path)


def _expand_batch(patterns: list[str]) -> list[Path]:
    result: list[Path] = []
    valid_extensions = {".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp", ".tiff", ".pdf"}
    for pattern in patterns:
        matches = glob_module.glob(pattern, recursive=True)
        if not matches:
            print(f"Warning: no files match '{pattern}'", file=sys.stderr)
        for m in sorted(matches):
            p = Path(m)
            if p.is_file() and p.suffix.lower() in valid_extensions:
                result.append(p)
    return result


def image_to_ascii(
    image_path: Path,
    width: Optional[int] = None,
    max_width: Optional[int] = None,
    charset: str = ASCII_CHARSET,
    invert: bool = False,
    binary: bool = False,
    aspect_correction: float = 0.75,
    threshold: Optional[int] = None,
    levels: Optional[int] = None,
    crop: Optional[tuple[int, int, int, int]] = None,
    progress: bool = False,
) -> str:
    img = Image.open(image_path)

    if crop:
        img = img.crop(crop)

    img_gray = img.convert("L")
    pixels_all = list(img_gray.get_flattened_data())

    if binary:
        if threshold is None:
            threshold = _otsu_threshold(pixels_all)
            if progress:
                print(f"  Otsu threshold: {threshold}", file=sys.stderr)
        img_gray = img_gray.point(lambda p: 255 if p > threshold else 0)

    w = _effective_width(width, img.width, max_width)
    aspect = img.height / img.width
    h = int(w * aspect * aspect_correction)

    if progress:
        print(f"  Resizing to {w}x{h}...", file=sys.stderr)

    img_gray = img_gray.resize((w, h), Image.Resampling.LANCZOS)
    pixels = list(img_gray.get_flattened_data())

    if levels is not None:
        chars = _make_charset(list(charset), levels)
    else:
        chars = list(charset)

    if invert:
        chars = list(reversed(chars))

    step = 256 / (len(chars) - 1) if len(chars) > 1 else 256

    lines = []
    for y in range(h):
        line_chars = []
        for x in range(w):
            brightness = pixels[y * w + x]
            idx = min(int(brightness / step), len(chars) - 1)
            line_chars.append(chars[idx])
        lines.append("".join(line_chars))

    if progress:
        print(f"  ASCII art generated ({w}x{h})", file=sys.stderr)

    return "\n".join(lines)


def _closest_color(r: int, g: int, b: int) -> str:
    best = "W"
    best_dist = float("inf")
    for code, (cr, cg, cb) in NAMED_COLORS.items():
        dist = (r - cr) ** 2 + (g - cg) ** 2 + (b - cb) ** 2
        if dist < best_dist:
            best_dist = dist
            best = code
    return best


def _color_name(code: str) -> str:
    return COLOR_NAMES_RU.get(code, code)


def _load_image_rgb(image_path: Path) -> Image.Image:
    img = Image.open(image_path)
    if img.mode == "RGBA":
        bg = Image.new("RGB", img.size, (255, 255, 255))
        bg.paste(img, mask=img.split()[3])
        return bg
    if img.mode != "RGB":
        return img.convert("RGB")
    return img


def analyze_colors(
    image_path: Path,
    grid_cols: int = 20,
    grid_rows: int = 15,
) -> tuple[str, str]:
    img = _load_image_rgb(image_path)
    orig_w, orig_h = img.size

    block_w = orig_w / grid_cols
    block_h = orig_h / grid_rows

    grid: list[list[str]] = []
    palette: set[str] = set()

    for gy in range(grid_rows):
        row: list[str] = []
        for gx in range(grid_cols):
            x0 = int(gx * block_w)
            y0 = int(gy * block_h)
            x1 = min(int((gx + 1) * block_w), orig_w)
            y1 = min(int((gy + 1) * block_h), orig_h)

            if x1 <= x0 or y1 <= y0:
                row.append("W")
                palette.add("W")
                continue

            crop = img.crop((x0, y0, x1, y1))
            pixels = list(crop.get_flattened_data())
            if not pixels:
                row.append("W")
                palette.add("W")
                continue

            avg_r = sum(p[0] for p in pixels) // len(pixels)
            avg_g = sum(p[1] for p in pixels) // len(pixels)
            avg_b = sum(p[2] for p in pixels) // len(pixels)

            code = _closest_color(avg_r, avg_g, avg_b)
            row.append(code)
            palette.add(code)

        grid.append(row)

    grid_text = "\n".join("".join(row) for row in grid)

    legend_lines = []
    for code in sorted(palette):
        legend_lines.append(f"  {code} = {_color_name(code)}")
    legend = "\n".join(legend_lines)

    return grid_text, legend


def run_ocr(image_path: Path, lang: str = "rus+eng") -> Optional[str]:
    if not _check_pytesseract():
        _warn_ocr("pytesseract not installed; install with: pip install pytesseract")
        return None
    import pytesseract
    img = _load_image_rgb(image_path)
    data = pytesseract.image_to_data(img, lang=lang, output_type=pytesseract.Output.DICT)
    lines: list[str] = []
    current_line: list[str] = []
    prev_block = -1
    prev_par = -1
    for i in range(len(data["text"])):
        text = data["text"][i].strip()
        if not text:
            continue
        block_num = data["block_num"][i]
        par_num = data["par_num"][i]
        if block_num != prev_block or par_num != prev_par:
            if current_line:
                lines.append(" ".join(current_line))
                current_line = []
        current_line.append(text)
        prev_block = block_num
        prev_par = par_num
    if current_line:
        lines.append(" ".join(current_line))
    return "\n".join(lines)


def run_ocr_with_positions(
    image_path: Path, lang: str = "rus+eng"
) -> Optional[list[dict]]:
    if not _check_pytesseract():
        _warn_ocr("pytesseract not installed; install with: pip install pytesseract")
        return None
    import pytesseract
    img = _load_image_rgb(image_path)
    data = pytesseract.image_to_data(img, lang=lang, output_type=pytesseract.Output.DICT)
    blocks: list[dict] = []
    current_text_parts: list[str] = []
    min_x = img.width
    min_y = img.height
    max_x = 0
    max_y = 0
    prev_block = -1
    prev_par = -1
    for i in range(len(data["text"])):
        text = data["text"][i].strip()
        if not text:
            continue
        block_num = data["block_num"][i]
        par_num = data["par_num"][i]
        x = data["left"][i]
        y = data["top"][i]
        w = data["width"][i]
        h = data["height"][i]
        if block_num != prev_block or par_num != prev_par:
            if current_text_parts:
                blocks.append({
                    "text": " ".join(current_text_parts),
                    "x": min_x,
                    "y": min_y,
                    "w": max_x + data["width"][i - 1] - min_x,
                    "h": max_y + data["height"][i - 1] - min_y,
                })
                current_text_parts = []
            min_x = x
            min_y = y
            max_x = x + w
            max_y = y + h
        else:
            min_x = min(min_x, x)
            min_y = min(min_y, y)
            max_x = max(max_x, x + w)
            max_y = max(max_y, y + h)
        current_text_parts.append(text)
        prev_block = block_num
        prev_par = par_num
    if current_text_parts:
        blocks.append({
            "text": " ".join(current_text_parts),
            "x": min_x,
            "y": min_y,
            "w": max_x - min_x,
            "h": max_y - min_y,
        })
    return blocks


def annotate_ascii(
    image_path: Path,
    width: int,
    aspect_correction: float = 0.5,
    ocr_lang: str = "rus+eng",
) -> str:
    img = Image.open(image_path)
    orig_w, orig_h = img.width, img.height
    img.close()

    aspect = orig_h / orig_w
    height = int(width * aspect * aspect_correction)

    scale_x = width / orig_w
    scale_y = height / orig_h

    blocks = run_ocr_with_positions(image_path, lang=ocr_lang)
    if blocks is None:
        return "[pytesseract not available]"
    if not blocks:
        return "[no OCR text found]"

    row_labels: dict[int, list[str]] = {}
    for b in blocks:
        center_y = int((b["y"] + b["h"] / 2) * scale_y)
        center_y = max(0, min(height - 1, center_y))
        row_labels.setdefault(center_y, []).append(b["text"])

    return _format_annotations(row_labels)


def _format_annotations(row_labels: dict[int, list[str]]) -> str:
    lines = []
    lines.append(f"{'Row':>5} \u2502 Label")
    lines.append(f"{'\u2500' * 5}\u2500\u253c{'\u2500' * 40}")
    for row in sorted(row_labels):
        labels = row_labels[row]
        for label in labels:
            lines.append(f"{row:>5} \u2502 {label}")
    return "\n".join(lines)


def _get_cached_ocr(
    image_path: Path, ocr_lang: str = "rus+eng"
) -> Optional[list[dict]]:
    cache_key = (str(image_path.resolve()), ocr_lang)
    if cache_key not in _ocr_cache:
        _ocr_cache[cache_key] = run_ocr_with_positions(image_path, lang=ocr_lang)
    return _ocr_cache[cache_key]


def annotate_and_merge(
    image_path: Path,
    ascii_art: str,
    width: int,
    aspect_correction: float = 0.5,
    ocr_lang: str = "rus+eng",
) -> str:
    img = Image.open(image_path)
    orig_w, orig_h = img.width, img.height
    img.close()

    aspect = orig_h / orig_w
    height = int(width * aspect * aspect_correction)

    scale_x = width / orig_w
    scale_y = height / orig_h

    blocks = _get_cached_ocr(image_path, lang=ocr_lang)
    if blocks is None:
        return ascii_art
    if not blocks:
        return ascii_art

    row_labels: dict[int, list[str]] = {}
    for b in blocks:
        center_y = int((b["y"] + b["h"] / 2) * scale_y)
        center_y = max(0, min(height - 1, center_y))
        row_labels.setdefault(center_y, []).append(b["text"])

    ascii_lines = ascii_art.split("\n")
    result_lines = []
    label_width = 40

    for row_idx, line in enumerate(ascii_lines):
        if row_idx in row_labels:
            label = " \u2502 " + " | ".join(row_labels[row_idx])
            result_lines.append(line + " " * max(1, label_width - len(line)) + label)
        else:
            result_lines.append(line)

    return "\n".join(result_lines)


def _process_single(args: argparse.Namespace, image_path: Path) -> None:
    _ocr_cache.clear()

    if not image_path.exists():
        print(f"Error: file '{image_path}' not found", file=sys.stderr)
        sys.exit(1)

    img_orig = Image.open(image_path)
    if args.auto_orient:
        img_orig = ImageOps.exif_transpose(img_orig)
    orig_w, orig_h = img_orig.width, img_orig.height
    exif_info = _get_exif_info(img_orig) if args.exif else {}
    img_orig.close()

    stem = image_path.stem
    charset = BLOCK_CHARSET if args.blocks else args.charset

    if args.levels is not None:
        charset = _make_charset(charset, args.levels)

    widths = args.multi if args.multi else [args.width]

    output_parts = []
    if args.md:
        output_parts.append(f"<!-- {orig_w}x{orig_h}px -->")
    else:
        output_parts.append(f"# Image: {orig_w}x{orig_h}px")

    if args.exif and exif_info:
        output_parts.append(_format_exif(exif_info))

    if args.ocr and not args.annotate:
        ocr_text = run_ocr(image_path, lang=args.ocr_lang)
        if ocr_text is not None:
            if args.md:
                output_parts.append("## OCR Text\n```text\n" + ocr_text + "\n```")
            else:
                output_parts.append("## OCR Text\n" + ocr_text)

    if args.colors:
        cols = args.color_grid
        rows = max(1, int(cols * orig_h / orig_w * 0.5))

        color_grid, color_legend = analyze_colors(image_path, grid_cols=cols, grid_rows=rows)
        if args.md:
            output_parts.append(
                "## Color Map\n"
                + "**Legend:**\n```text\n"
                + color_legend
                + "\n```\n\n**Grid:** ("
                + f"{cols}x{rows}"
                + ")\n```text\n"
                + color_grid
                + "\n```"
            )
        else:
            output_parts.append(
                "## Color Map\nLegend:\n"
                + color_legend
                + f"\n\nGrid: ({cols}x{rows})\n"
                + color_grid
            )

    if args.ocr_only:
        final_output = "\n\n".join(output_parts)
        out_path = _resolve_output(args, image_path, stem, "ocr.md")
        if out_path:
            out_path.write_text(final_output, encoding="utf-8")
            print(f"Saved to {out_path}")
        else:
            print(final_output)
        return

    results: list[tuple[int, str]] = []
    for w in widths:
        used_w = _effective_width(w, orig_w, args.max_width)
        if args.progress:
            print(f"Processing width={used_w}...", file=sys.stderr)

        result = image_to_ascii(
            image_path=image_path,
            width=w,
            max_width=args.max_width,
            charset=charset,
            invert=args.invert,
            binary=args.binary,
            aspect_correction=args.aspect,
            threshold=args.threshold,
            levels=args.levels,
            crop=args.crop,
            progress=args.progress,
        )

        if args.annotate:
            result = annotate_and_merge(
                image_path=image_path,
                ascii_art=result,
                width=used_w,
                aspect_correction=args.aspect,
                ocr_lang=args.ocr_lang,
            )

        results.append((used_w, result))

    for used_w, result in results:
        if args.multi:
            if args.md:
                output_parts.append(f"<!-- width={used_w} -->")
            else:
                output_parts.append(f"## Width: {used_w} chars")
        output_parts.append(f"```\n{result}\n```" if args.md else result)

    final_output = "\n\n".join(output_parts)
    sizes = ", ".join(f"{w}ch" for w, _ in results)
    flags = []
    if args.ocr:
        flags.append("+ocr")
    if args.annotate:
        flags.append("+annotate")
    if args.colors:
        flags.append("+colors")
    if args.exif:
        flags.append("+exif")

    out_path = _resolve_output(args, image_path, stem, "output.md")
    if out_path:
        out_path.write_text(final_output, encoding="utf-8")
        print(f"Saved to {out_path} (sizes: {sizes}, original: {orig_w}x{orig_h}px{''.join(flags)})")
    else:
        print(final_output)


def _resolve_output(
    args: argparse.Namespace, image_path: Path, stem: str, filename: str
) -> Optional[Path]:
    if args.no_dir:
        return None
    if args.output:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        return out
    out_dir = image_path.parent / stem
    out_dir.mkdir(parents=True, exist_ok=True)
    if not args.overwrite:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        name, ext = os.path.splitext(filename)
        filename = f"{name}_{ts}{ext}"
    return out_dir / filename


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Convert image to super large ASCII art for LLM recognition"
    )
    parser.add_argument(
        "image", type=str, nargs="?", default=None,
        help="Path to input image, '-' for stdin, or glob pattern with --batch"
    )
    parser.add_argument(
        "-w", "--width", type=int, default=None,
        help="Output width in characters (default: original image width)"
    )
    parser.add_argument(
        "--max-width", type=int, default=None,
        help="Cap width at this value when auto-detecting"
    )
    parser.add_argument(
        "-o", "--output", type=str, default=None,
        help="Output file path (default: auto-generated folder next to image)"
    )
    parser.add_argument(
        "-c", "--charset", type=str, default=ASCII_CHARSET,
        help="Characters dark-to-light (default: %(default)s)"
    )
    parser.add_argument(
        "-b", "--blocks", action="store_true",
        help="Use Unicode block chars ( ░▒▓█) instead of ASCII"
    )
    parser.add_argument(
        "--invert", action="store_true",
        help="Invert charset (light background)"
    )
    parser.add_argument(
        "--binary", action="store_true",
        help="Threshold to pure black/white (good for text/diagrams)"
    )
    parser.add_argument(
        "--threshold", type=int, default=None,
        help="Binary threshold 0-255 (default: Otsu auto-threshold)"
    )
    parser.add_argument(
        "--levels", type=int, default=None,
        help="Number of gradation levels (default: 10, max: 70 for extended charset)"
    )
    parser.add_argument(
        "-a", "--aspect", type=float, default=0.75,
        help="Aspect ratio correction (default: 0.75, use 0.5 for terminal)"
    )
    parser.add_argument(
        "--multi", nargs="+", type=int, default=None,
        help="Generate multiple widths at once, e.g. --multi 80 150 300"
    )
    parser.add_argument(
        "--md", action=argparse.BooleanOptionalAction, default=True,
        help="Wrap output in markdown code block"
    )
    parser.add_argument(
        "--ocr", action="store_true",
        help="Run OCR and include recognized text"
    )
    parser.add_argument(
        "--ocr-lang", type=str, default="rus+eng",
        help="OCR language (default: rus+eng)"
    )
    parser.add_argument(
        "--ocr-only", action="store_true",
        help="Output only OCR text, no ASCII art"
    )
    parser.add_argument(
        "--annotate", action="store_true",
        help="Place OCR labels next to matching ASCII rows"
    )
    parser.add_argument(
        "--colors", action="store_true",
        help="Include color analysis grid and palette"
    )
    parser.add_argument(
        "--color-grid", type=int, default=20,
        help="Color grid resolution (default: 20 cols, auto rows)"
    )
    parser.add_argument(
        "--no-dir", action="store_true",
        help="Print to stdout instead of saving to auto-created folder"
    )
    parser.add_argument(
        "--batch", action="store_true",
        help="Treat image argument as glob pattern; process all matches"
    )
    parser.add_argument(
        "--overwrite", action="store_true",
        help="Overwrite output file instead of appending timestamp"
    )
    parser.add_argument(
        "--auto-orient", action="store_true",
        help="Auto-rotate image according to EXIF orientation"
    )
    parser.add_argument(
        "--exif", action="store_true",
        help="Extract and include EXIF metadata in output"
    )
    parser.add_argument(
        "--progress", action="store_true",
        help="Show processing progress on stderr"
    )
    parser.add_argument(
        "--crop", type=_parse_crop, default=None,
        metavar="X,Y,W,H",
        help="Crop region before processing (e.g. 0,0,500,400)"
    )

    args = parser.parse_args()

    if args.image is None or args.image == "-":
        if not sys.stdin.isatty():
            image_path = _read_stdin()
            _process_single(args, image_path)
            return
        else:
            parser.print_help()
            sys.exit(1)

    if args.batch:
        files = _expand_batch([args.image])
        if not files:
            print(f"Error: no files matched pattern '{args.image}'", file=sys.stderr)
            sys.exit(1)
        for f in files:
            print(f"=== {f.name} ===", file=sys.stderr)
            _process_single(args, f)
        return

    image_path = Path(args.image).resolve()

    if image_path.suffix.lower() == ".pdf":
        pdf_pages = _handle_pdf(image_path)
        for page_path in pdf_pages:
            print(f"=== Page: {page_path.name} ===", file=sys.stderr)
            _process_single(args, page_path)
        return

    _process_single(args, image_path)


if __name__ == "__main__":
    main()