from __future__ import annotations

import shutil
import re
import uuid
import zipfile
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple

from lxml import etree

from app.services.formula_ocr import FormulaOCR
from app.services.omml_converter import OmmlConverter

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
M_NS = "http://schemas.openxmlformats.org/officeDocument/2006/math"
PKG_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"

NSMAP = {"w": W_NS, "a": A_NS, "r": R_NS, "m": M_NS}


@dataclass
class ConversionStats:
    omml_found: int = 0
    image_formula_found: int = 0
    text_latex_found: int = 0
    replaced: int = 0


class DocxFormulaProcessor:
    _TEXT_LATEX_PATTERN = re.compile(
        r"\$\$(?P<block>.+?)\$\$"
        r"|\\\[(?P<bracket>.+?)\\\]"
        r"|\\\((?P<paren>.+?)\\\)"
        r"|(?<!\$)\$(?P<inline>[^\n$]+?)\$(?!\$)",
        flags=re.DOTALL,
    )

    def __init__(self) -> None:
        self._ocr = FormulaOCR()
        self._omml = OmmlConverter()

    def process(self, input_docx: Path, output_docx: Path) -> ConversionStats:
        stats = ConversionStats()
        work_dir = output_docx.parent / f"tmp_{uuid.uuid4().hex}"
        if work_dir.exists():
            shutil.rmtree(work_dir)
        work_dir.mkdir(parents=True, exist_ok=True)

        try:
            with zipfile.ZipFile(input_docx, "r") as zin:
                zin.extractall(work_dir)

            story_parts = self._find_story_parts(work_dir)
            for part in story_parts:
                tree = etree.parse(str(part))
                root = tree.getroot()
                rel_map = self._read_relationship_map(work_dir, part)

                omml_nodes = root.findall(".//m:oMath", namespaces=NSMAP)
                stats.omml_found += len(omml_nodes)

                img_replaced = self._replace_formula_images(root, rel_map, work_dir, part)
                stats.image_formula_found += img_replaced
                stats.replaced += img_replaced

                text_found, text_replaced = self._replace_text_latex_formulas(root)
                stats.text_latex_found += text_found
                stats.replaced += text_replaced

                tree.write(
                    str(part),
                    encoding="utf-8",
                    xml_declaration=True,
                    standalone="yes",
                )

            if output_docx.exists():
                output_docx.unlink()
            with zipfile.ZipFile(output_docx, "w", zipfile.ZIP_DEFLATED) as zout:
                for p in work_dir.rglob("*"):
                    if p.is_file():
                        arcname = p.relative_to(work_dir)
                        zout.write(p, arcname.as_posix())
            return stats
        finally:
            shutil.rmtree(work_dir, ignore_errors=True)

    def _find_story_parts(self, work_dir: Path) -> List[Path]:
        word_dir = work_dir / "word"
        if not word_dir.exists():
            return []
        patterns = ["document.xml", "header*.xml", "footer*.xml", "footnotes.xml", "endnotes.xml"]
        parts: List[Path] = []
        for pattern in patterns:
            parts.extend(word_dir.glob(pattern))
        return parts

    def _read_relationship_map(self, work_dir: Path, part_path: Path) -> Dict[str, str]:
        rel_path = part_path.parent / "_rels" / f"{part_path.name}.rels"
        if not rel_path.exists():
            return {}
        tree = etree.parse(str(rel_path))
        root = tree.getroot()
        rel_map: Dict[str, str] = {}
        for rel in root.findall(f".//{{{PKG_REL_NS}}}Relationship"):
            r_id = rel.get("Id")
            target = rel.get("Target")
            if r_id and target:
                rel_map[r_id] = target
        return rel_map

    def _resolve_target(self, story_part: Path, target: str, work_dir: Path) -> Path:
        base = story_part.parent
        candidate = (base / target).resolve()
        try:
            candidate.relative_to(work_dir.resolve())
            return candidate
        except Exception:
            return (work_dir / "word" / target.replace("../", "")).resolve()

    def _replace_formula_images(
        self,
        root: etree._Element,
        rel_map: Dict[str, str],
        work_dir: Path,
        story_part: Path,
    ) -> int:
        replaced = 0
        runs_with_drawing = root.findall(".//w:r[w:drawing]", namespaces=NSMAP)
        for run in runs_with_drawing:
            drawing = run.find("w:drawing", namespaces=NSMAP)
            if drawing is None:
                continue
            blip = drawing.find(".//a:blip", namespaces=NSMAP)
            if blip is None:
                continue
            r_id = blip.get(f"{{{R_NS}}}embed")
            if not r_id:
                continue
            target = rel_map.get(r_id)
            if not target:
                continue

            img_path = self._resolve_target(story_part, target, work_dir)
            if not img_path.exists():
                continue
            if not self._ocr.is_formula_like_image(img_path):
                continue

            ocr_result = self._ocr.extract_latex(img_path)
            if ocr_result is None:
                continue
            if ocr_result.confidence < 0.4:
                continue

            parent = run.getparent()
            if parent is None:
                continue

            try:
                prepared_latex = self._omml.prepare_latex_for_word(ocr_result.latex)
                new_node = self._omml.latex_to_omml(prepared_latex)
            except Exception:
                continue
            parent.replace(run, new_node)
            replaced += 1
        return replaced

    def _replace_text_latex_formulas(self, root: etree._Element) -> tuple[int, int]:
        found = 0
        replaced = 0
        paragraphs = root.findall(".//w:p", namespaces=NSMAP)
        for paragraph in paragraphs:
            para_found, para_replaced = self._replace_text_latex_in_paragraph(paragraph)
            found += para_found
            replaced += para_replaced
        return found, replaced

    def _replace_text_latex_in_paragraph(self, paragraph: etree._Element) -> tuple[int, int]:
        found = 0
        replaced = 0
        children = list(paragraph)
        if not children:
            return found, replaced

        new_children: List[etree._Element] = []
        run_buffer: List[etree._Element] = []

        def flush_buffer() -> None:
            nonlocal found, replaced
            if not run_buffer:
                return
            nodes, local_found, local_replaced = self._replace_text_latex_in_run_buffer(run_buffer)
            new_children.extend(nodes)
            found += local_found
            replaced += local_replaced
            run_buffer.clear()

        for child in children:
            if child.tag == f"{{{W_NS}}}r" and self._is_text_run(child):
                run_buffer.append(child)
            else:
                flush_buffer()
                new_children.append(child)

        flush_buffer()

        if found > 0:
            for child in list(paragraph):
                paragraph.remove(child)
            for child in new_children:
                paragraph.append(child)

        return found, replaced

    def _replace_text_latex_in_run_buffer(
        self,
        runs: List[etree._Element],
    ) -> Tuple[List[etree._Element], int, int]:
        texts = [self._extract_run_text(run) for run in runs]
        all_text = "".join(texts)
        if not all_text:
            return runs, 0, 0
        if "$" not in all_text and "\\(" not in all_text and "\\[" not in all_text:
            return runs, 0, 0

        matches = list(self._TEXT_LATEX_PATTERN.finditer(all_text))
        if not matches:
            return runs, 0, 0

        run_spans: List[Tuple[int, int]] = []
        cursor = 0
        for text in texts:
            start = cursor
            cursor += len(text)
            run_spans.append((start, cursor))

        result_nodes: List[etree._Element] = []
        found = len(matches)
        replaced = 0
        last_end = 0

        for match in matches:
            start, end = match.span()
            if start > last_end:
                result_nodes.extend(self._slice_runs_text(runs, texts, run_spans, last_end, start))

            latex_raw = (
                match.group("block")
                or match.group("bracket")
                or match.group("paren")
                or match.group("inline")
                or ""
            )
            latex = self._normalize_latex(latex_raw)
            if latex:
                try:
                    prepared_latex = self._omml.prepare_latex_for_word(latex)
                    result_nodes.append(self._omml.latex_to_omml(prepared_latex))
                    replaced += 1
                except Exception:
                    result_nodes.extend(self._slice_runs_text(runs, texts, run_spans, start, end))
            else:
                result_nodes.extend(self._slice_runs_text(runs, texts, run_spans, start, end))

            last_end = end

        if last_end < len(all_text):
            result_nodes.extend(self._slice_runs_text(runs, texts, run_spans, last_end, len(all_text)))

        return result_nodes, found, replaced

    def _slice_runs_text(
        self,
        runs: List[etree._Element],
        texts: List[str],
        run_spans: List[Tuple[int, int]],
        seg_start: int,
        seg_end: int,
    ) -> List[etree._Element]:
        result: List[etree._Element] = []
        if seg_start >= seg_end:
            return result
        for i, (run_start, run_end) in enumerate(run_spans):
            if run_end <= seg_start or run_start >= seg_end:
                continue
            local_start = max(seg_start, run_start) - run_start
            local_end = min(seg_end, run_end) - run_start
            if local_start >= local_end:
                continue
            piece = texts[i][local_start:local_end]
            node = self._clone_run_with_text(runs[i], piece)
            if node is not None:
                result.append(node)
        return result

    def _is_text_run(self, run: etree._Element) -> bool:
        if run.find("w:drawing", namespaces=NSMAP) is not None:
            return False
        return run.find("w:t", namespaces=NSMAP) is not None

    def _extract_run_text(self, run: etree._Element) -> str:
        ts = run.findall("w:t", namespaces=NSMAP)
        if not ts:
            return ""
        return "".join(t.text or "" for t in ts)

    def _clone_run_with_text(self, source_run: etree._Element, text: str) -> etree._Element | None:
        if text == "":
            return None
        run = etree.Element(f"{{{W_NS}}}r")
        rpr = source_run.find("w:rPr", namespaces=NSMAP)
        if rpr is not None:
            run.append(deepcopy(rpr))
        t = etree.SubElement(run, f"{{{W_NS}}}t")
        if text.strip() != text or "  " in text:
            t.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
        t.text = text
        return run

    def _normalize_latex(self, text: str) -> str:
        normalized = (text or "").replace("\r\n", "\n").strip()
        return normalized
