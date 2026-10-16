"""递归字符分块器（RecursiveCharacterTextSplitter 思想的手写实现）。

核心概念——"递归"指的是分隔符优先级逐级降级，不是函数自调用：
    段落(\\n\\n) → 行(\\n) → 句号 → 叹/问号 → 分号 → 逗号 → 空格 → 硬切
优先在语义最完整的边界下刀；边界不够密（块仍超长）才降级到更碎的边界。

两条原则：
1. 不把句子腰斩——所以有 overlap：前一块的尾巴复制进下一块开头，
   跨块的关键句在两侧都完整可读。
2. 不丢字——split 时把分隔符"扔掉"了，merge 时靠 pieces 顺序重新拼，
   中文句子级分隔符（。！？）在降级路径上会丢失，v1 接受此近似。
"""

SEPARATORS = ["\n\n", "\n", "。", "！", "？", "；", "，", " ", ""]

def split_text(text: str, chunk_size: int = 500, overlap: int = 80) -> list[str]:
    """把长文本切成不超过 chunk_size 的块，相邻块重叠 overlap 个字符。"""
    if chunk_size <= 0:
        raise ValueError("chunk_size 必须大于 0")
    if not 0 <= overlap < chunk_size:
        raise ValueError("overlap 必须满足 0 <= overlap < chunk_size")

    pieces: list[str] = []
    _split(text, SEPARATORS, chunk_size, pieces)
    return _merge_with_overlap(pieces, chunk_size, overlap)


def _split(text: str, seps: list[str], size: int, out: list[str]) -> None:
    """按当前级分隔符切；还超长的片段，降级用下一级继续切。"""
    sep = seps[0]
    parts = [p for p in text.split(sep) if p.strip()] if sep else [text]
    for p in parts:
        if len(p) <= size or len(seps) <= 1:
            out.append(p)
        else:
            _split(p, seps[1:], size, out)


def _merge_with_overlap(pieces: list[str], size: int, overlap: int) -> list[str]:
    """把碎片贪心地攒成块：装得下就继续装，装不下就封块，
    并把封块尾部 overlap 个字符带入下一块开头。"""
    chunks: list[str] = []
    cur = ""
    for p in pieces:
        if cur and len(cur) + len(p) > size:
            chunks.append(cur)
            cur = cur[-overlap:] if overlap else ""
        cur = (cur + p) if cur else p
        while len(cur) > size:          # 单块本身就超长（降级后仍超长）→ 硬切
            chunks.append(cur[:size])
            cur = cur[size:]
    if cur.strip():
        chunks.append(cur)
    return [c.strip() for c in chunks if c.strip()]