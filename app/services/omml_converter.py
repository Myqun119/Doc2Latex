from __future__ import annotations

import re

from lxml import etree

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
M_NS = "http://schemas.openxmlformats.org/officeDocument/2006/math"


class OmmlConverter:
    _BARE_AMP_PATTERN = re.compile(r"&(?!#?[A-Za-z0-9]+;)")

    def __init__(self) -> None:
        self._has_mathml2omml = False
        self._mathml2omml_callable = None
        try:
            import mathml2omml  # type: ignore

            convert = getattr(mathml2omml, "convert", None)
            if callable(convert):
                self._mathml2omml_callable = convert
                self._has_mathml2omml = True
        except Exception:
            self._has_mathml2omml = False

    def latex_to_omml(self, latex: str) -> etree._Element:
        latex = self._prepare_latex_for_conversion(latex)
        if not latex:
            return self._fallback_text_run(" ")

        if self._has_mathml2omml and self._mathml2omml_callable is not None:
            try:
                import latex2mathml.converter  # type: ignore

                mathml = latex2mathml.converter.convert(latex)
                mathml = self._sanitize_mathml(mathml)
                omml_xml = self._mathml2omml_callable(mathml)
                omml_node = self._parse_omml_xml(omml_xml)
                return self._ensure_omathpara(omml_node)
            except Exception:
                pass

        return self._fallback_text_run(f"${latex}$")

    def validate_latex_for_word(self, latex: str) -> tuple[bool, str]:
        try:
            prepared = self._prepare_latex_for_conversion(latex)
            node = self.latex_to_omml(prepared)
            tag_ok = node.tag in {f"{{{M_NS}}}oMath", f"{{{M_NS}}}oMathPara"}
            if not tag_ok:
                return False, "未生成 Word 原生公式节点"

            root = etree.Element(f"{{{W_NS}}}document", nsmap={"w": W_NS, "m": M_NS})
            body = etree.SubElement(root, f"{{{W_NS}}}body")
            p = etree.SubElement(body, f"{{{W_NS}}}p")
            p.append(node)
            etree.tostring(root, encoding="utf-8", xml_declaration=True)
            return True, "可转换为 Word 原生公式"
        except Exception as exc:
            return False, f"转换失败: {exc}"

    def prepare_latex_for_word(self, latex: str) -> str:
        return self._prepare_latex_for_conversion(latex)

    def _prepare_latex_for_conversion(self, latex: str) -> str:
        normalized = (latex or "").strip()
        if not normalized:
            return ""

        normalized = self._normalize_supported_commands(normalized)
        self._validate_latex_syntax(normalized)
        return normalized

    def _normalize_supported_commands(self, latex: str) -> str:
        # pmb is often used as bold symbol; map to a better-supported equivalent.
        return latex.replace("\\pmb", "\\mathbf")

    def _validate_latex_syntax(self, latex: str) -> None:
        brace_depth = 0
        env_stack: list[str] = []
        i = 0
        while i < len(latex):
            char = latex[i]
            if char == "\\":
                token = self._read_command(latex, i)
                if token in {"begin", "end"}:
                    env_name, consumed = self._read_braced_argument(latex, i + len(token) + 1)
                    if not env_name:
                        raise ValueError("LaTeX 环境缺少名称")
                    if token == "begin":
                        env_stack.append(env_name)
                    else:
                        if not env_stack or env_stack[-1] != env_name:
                            raise ValueError(f"LaTeX 环境不匹配: {env_name}")
                        env_stack.pop()
                    i += len(token) + consumed + 1
                    continue
                i += len(token) + 1
                continue

            if char == "{":
                brace_depth += 1
            elif char == "}":
                brace_depth -= 1
                if brace_depth < 0:
                    raise ValueError("LaTeX 大括号不匹配")
            i += 1

        if brace_depth != 0:
            raise ValueError("LaTeX 大括号未闭合")
        if env_stack:
            raise ValueError(f"LaTeX 环境未闭合: {env_stack[-1]}")

    def _read_command(self, latex: str, start: int) -> str:
        idx = start + 1
        command_chars: list[str] = []
        while idx < len(latex) and latex[idx].isalpha():
            command_chars.append(latex[idx])
            idx += 1
        return "".join(command_chars)

    def _read_braced_argument(self, latex: str, start: int) -> tuple[str, int]:
        if start >= len(latex) or latex[start] != "{":
            return "", 0
        depth = 0
        chars: list[str] = []
        idx = start
        while idx < len(latex):
            char = latex[idx]
            if char == "{":
                depth += 1
                if depth > 1:
                    chars.append(char)
            elif char == "}":
                depth -= 1
                if depth == 0:
                    return "".join(chars), idx - start + 1
                chars.append(char)
            else:
                chars.append(char)
            idx += 1
        return "", 0

    def _ensure_omathpara(self, node: etree._Element) -> etree._Element:
        if node.tag == f"{{{M_NS}}}oMathPara":
            return node
        if node.tag == f"{{{M_NS}}}oMath":
            para = etree.Element(f"{{{M_NS}}}oMathPara", nsmap={"m": M_NS})
            para.append(node)
            return para
        found = node.find(f".//{{{M_NS}}}oMathPara")
        if found is not None:
            return found
        found_omath = node.find(f".//{{{M_NS}}}oMath")
        if found_omath is not None:
            para = etree.Element(f"{{{M_NS}}}oMathPara", nsmap={"m": M_NS})
            para.append(found_omath)
            return para
        return self._fallback_text_run(" ")

    def _parse_omml_xml(self, omml_xml: str) -> etree._Element:
        xml_text = (omml_xml or "").strip()
        if not xml_text:
            raise ValueError("Empty OMML xml")

        parser = etree.XMLParser(recover=True)
        if "xmlns:m=" not in xml_text and "<m:" in xml_text:
            wrapped = f"<root xmlns:m=\"{M_NS}\">{xml_text}</root>"
            wrapper = etree.fromstring(wrapped.encode("utf-8"), parser=parser)
            if len(wrapper) == 0:
                raise ValueError("Invalid OMML xml")
            return wrapper[0]

        return etree.fromstring(xml_text.encode("utf-8"), parser=parser)

    def _sanitize_mathml(self, mathml: str) -> str:
        if not mathml:
            return ""
        return self._BARE_AMP_PATTERN.sub("&amp;", mathml)

    def _fallback_text_run(self, text: str) -> etree._Element:
        para = etree.Element(f"{{{W_NS}}}r", nsmap={"w": W_NS})
        t = etree.SubElement(para, f"{{{W_NS}}}t")
        t.text = text
        return para
