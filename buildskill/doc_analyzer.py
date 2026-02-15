"""
文档元知识分析模块
采用三智能体架构：Agent1(Level1)、Agent2(Level2)、Agent3(评审专家)
"""

import os
import re
import ssl
import time
from pathlib import Path
from dataclasses import dataclass, field

# 可重试的异常类型（网络/SSL 瞬时错误）
RETRY_EXCEPTIONS = (ssl.SSLEOFError, ssl.SSLError, ConnectionError, TimeoutError, OSError)


# 支持的文档扩展名（文本 + Word + PDF + 图片）
DOC_EXTENSIONS = {".md", ".txt", ".rst", ".docx", ".pdf", ".png", ".jpg", ".jpeg", ".gif", ".webp"}

# 多模态文件 MIME 类型
MIME_TYPES = {
    ".pdf": "application/pdf",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
}

# 评审 8 维度：名称, 权重
REVIEW_DIMENSIONS = [
    ("事实准确性", 0.20),
    ("来源可信度", 0.15),
    ("分析深度与逻辑性", 0.20),
    ("客观性与偏见控制", 0.15),
    ("全面性与覆盖度", 0.10),
    ("时效性与前瞻性", 0.10),
    ("清晰度与结构化", 0.05),
    ("实用价值与洞察力", 0.05),
]

# Agent1: 一级规范分析智能体
AGENT1_LEVEL1_PROMPT = """你是**文档结构与文体分析智能体（Agent1）**，专门负责对文档进行一级规范分析，提取表层写作规范与形式特征。

请以独立专家的身份，对以下文档进行系统分析。输出需包含以下 8 个维度（每个维度用 ## 二级标题）：

## 1. 文章结构
- 整体架构（如：总分总、递进式、并列式等）
- 章节层级与组织方式
- 段落间的逻辑关系

## 2. 章节规划
- 典型章节命名方式
- 章节长度与密度分布
- 章节间的过渡方式

## 3. 论点展开方式
- 论点提出方式（开门见山 / 层层递进等）
- 论点支撑逻辑
- 正反论证或多元视角的运用

## 4. 论据陈列方式
- 论据类型（数据、案例、引语、类比等）
- 论据的组织顺序
- 论据与论点的衔接方式

## 5. 语言风格
- 正式度与语域
- 句式特点（长短句比例、复杂句运用）
- 人称与视角

## 6. 常用词汇
- 领域术语
- 衔接词与过渡语
- 高频修饰语或限定词

## 7. 修辞手法
- 比喻、类比、排比等运用
- 强调与弱化策略
- 其他修辞特征

## 8. 引用规范
- 引用格式与位置
- 引用密度与分布
- 文献类型与权威性选择

请直接输出分析结果，不要输出前缀说明。

---
文档内容：
"""

# Agent2: 二级元语义分析智能体
AGENT2_LEVEL2_PROMPT = """你是**文档元逻辑与认知结构分析智能体（Agent2）**，专门负责对文档进行二级元语义分析，提取形而上的抽象认知模式与思维架构。

请以独立专家的身份，对以下文档进行系统分析。输出需包含以下 5 个维度（每个维度用 ## 二级标题）：

## 1. 概念构造方式
- 核心概念的界定与拆解方式
- 概念之间的层次与关系
- 抽象概念的具体化策略

## 2. 隐喻与比喻表达
- 使用的隐喻体系（如：空间隐喻、容器隐喻等）
- 比喻在论证中的角色
- 类比推理的运用模式

## 3. 论点递进手法
- 论证的层次与深度
- 从具体到抽象或从抽象到具体的路径
- 反驳与自我修正的结构

## 4. 分析角度选择
- 多角度切入的方式
- 视角切换的逻辑
- 主次角度的安排

## 5. 分析架构
- 整体认知框架（如：问题-方案、因果、比较等）
- 推理链的结构
- 结论生成的逻辑路径

请直接输出分析结果，不要输出前缀说明。

---
文档内容：
"""

# Agent3: 写作质量评审专家智能体
AGENT3_REVIEW_PROMPT = """你是**写作质量评审专家智能体（Agent3）**，负责在 Level1、Level2 分析基础上，结合源文档对写作质量进行专业评价。

请根据以下【源文档】、【Level1 分析】、【Level2 分析】，按 8 个核心维度独立打分（1~5 分）。最后输出「评分汇总」区块。

---

## 评分标准（必须严格遵循）

### 维度1：事实准确性（权重20%）
- 1分：大量明显错误
- 3分：基本正确但有个别疑点
- 5分：事实严谨且可验证

### 维度2：来源可信度（权重15%）
- 1分：来源模糊或低可信
- 5分：来源优质且注明出处

### 维度3：分析深度与逻辑性（权重20%）
- 1分：浅显罗列
- 5分：多角度深度剖析且推理严谨

### 维度4：客观性与偏见控制（权重15%）
- 1分：强烈偏见
- 5分：高度客观

### 维度5：全面性与覆盖度（权重10%）
- 1分：片面
- 5分：多维度全面（覆盖关键各方观点、产业链上下游、潜在风险与机遇）

### 维度6：时效性与前瞻性（权重10%）
- 1分：过时信息
- 5分：结合最新动态并有前瞻判断

### 维度7：清晰度与结构化（权重5%）
- 1分：混乱晦涩
- 5分：逻辑清晰且易读

### 维度8：实用价值与洞察力（权重5%）
- 1分：泛泛而谈
- 5分：高价值洞察，可为决策者提供独特、可操作的洞见

---

## 输出格式要求

请先输出各维度的简要评语（1-2 句），最后**必须**输出以下格式的「评分汇总」区块（便于程序解析）：

```
## 评分汇总
维度1-事实准确性: X
维度2-来源可信度: X
维度3-分析深度与逻辑性: X
维度4-客观性与偏见控制: X
维度5-全面性与覆盖度: X
维度6-时效性与前瞻性: X
维度7-清晰度与结构化: X
维度8-实用价值与洞察力: X
```

其中 X 为 1~5 的整数。

---

【源文档】
{source_content}

---

【Level1 分析】
{level1_content}

---

【Level2 分析】
{level2_content}

---

请输出评审结果：
"""

# 汇总归纳 prompt（融入评分）
SUMMARY_PROMPT = """你是一位写作规范与元知识萃取专家。以下是同一目录下多篇文档的：
1. Level1（一级规范）分析
2. Level2（二级元语义）分析
3. **写作质量评分结果**（8 维度 1~5 分，综合评分满分 5 分）

请完成以下任务：

1. **重点关注高分内容**：
   - 对**综合评分高**的文档（如 4.0 分以上），重点提炼其核心写作知识与技巧
   - 对**各维度中得分高的文档**（如某文档在「分析深度与逻辑性」得 5 分），提取该维度下的优秀实践
   
2. **归纳共通特征**：提取这些文档在 Level1 和 Level2 各维度上的共性规律

3. **分类与总结**：将共性按维度归类，形成清晰的结构化总结

4. **提炼写作指南**：基于归纳结果及高分文档的精华，形成可指导**同类文档写作**的实用指南，包括：
   - 结构建议
   - 论证范式
   - 语言与修辞规范
   - 元认知与思维框架建议
   - 质量标杆（参考高分文档的做法）

输出格式要求：
- 使用 Markdown
- 一级标题为「文档类型写作规范汇总」
- 二级标题对应各维度
- 在相关章节中**明确标注**哪些内容来自高分文档/高得分维度的提炼
- 内容具体、可操作，便于大模型或人类参考写作

---
Level1 分析汇总：
{level1_texts}

---
Level2 分析汇总：
{level2_texts}

---
评分结果汇总（文档名 | 各维度分 | 综合分）：
{score_summary}

---
请输出汇总分析文档：
"""

# 将汇总分析转为 Skill 的 prompt
SKILL_CONVERSION_PROMPT = """以下是一份「文档类型写作规范汇总」分析文档，其中包含来自高分文档与高得分维度的写作精华提炼。

请将其转换为 Cursor Agent 可用的 Skill 文件格式。

要求：
1. 输出必须包含 YAML frontmatter：
   ---
   name: <skill-name>（小写、连字符，如 doc-writing-academic）
   description: <简明描述，说明何时使用此 skill，最多 200 字>
   ---

2. 正文为 Markdown，结构包括：
   - # 标题
   - ## 结构规范
   - ## 论证与论据
   - ## 语言与修辞
   - ## 元认知与思维框架
   - ## 质量要点（整合高分文档的精华实践）
   - 各节内容从分析文档提炼为可执行的写作指导，面向大模型调用

3. 描述（description）需包含触发场景

4. 对「质量要点」或「质量标杆」相关章节给予充分篇幅，体现高分文档的写作智慧

5. 内容简洁、可操作，适合作为 Agent 的 system 级指导

---
汇总分析文档：
{summary_text}

---
请直接输出完整的 SKILL.md 内容：
"""


@dataclass
class DocAnalysisResult:
    """单文档分析结果"""
    doc_path: Path
    level1: str
    level2: str
    review: str = ""
    scores: dict[str, float] = field(default_factory=dict)
    weighted_score: float = 0.0


def _round_to_half(val: float) -> float:
    """四舍五入到 0.5 的倍数：4.3→4.5，4.2→4.0"""
    return round(val * 2) / 2


def _parse_review_scores(review_text: str) -> tuple[dict[str, float], float]:
    """从评审文本解析各维度分数，计算加权综合分"""
    dim_names = [d[0] for d in REVIEW_DIMENSIONS]
    scores = {}

    for i, name in enumerate(dim_names):
        # 匹配多种格式：维度N-名称: X / 名称: X / 维度N: X
        patterns = [
            rf"维度{i+1}[-－]\s*{re.escape(name)}\s*[:：]\s*(\d)",
            rf"{re.escape(name)}\s*[:：]\s*(\d)",
            rf"维度{i+1}\s*[:：]\s*(\d)",
        ]
        for pat in patterns:
            m = re.search(pat, review_text)
            if m:
                v = float(m.group(1))
                if 1 <= v <= 5:
                    scores[name] = v
                break

    if len(scores) != len(REVIEW_DIMENSIONS):
        return scores, 0.0

    weighted = sum(scores.get(n, 0) * w for n, w in REVIEW_DIMENSIONS)
    return scores, _round_to_half(weighted)


def _is_multimodal(path: Path) -> bool:
    """是否为多模态文件（PDF、图片），需直接传给 API"""
    return path.suffix.lower() in MIME_TYPES


def _get_mime_type(path: Path) -> str | None:
    return MIME_TYPES.get(path.suffix.lower())


def _read_doc(path: Path) -> str:
    """读取文档内容。多模态文件（PDF/图片）不在此解析，由 API 直接处理。"""
    ext = path.suffix.lower()
    try:
        if ext == ".docx":
            try:
                import docx
                doc = docx.Document(path)
                return "\n".join(p.text for p in doc.paragraphs)
            except ImportError:
                return f"[需安装 python-docx 以读取 .docx: {path}]"
        if ext in MIME_TYPES:
            return ""  # 多模态由 _call_llm_with_file 处理
        return path.read_text(encoding="utf-8", errors="ignore")
    except Exception as e:
        return f"[读取失败: {e}]"


def _get_doc_files(doc_dir: Path) -> list[Path]:
    """获取目录下所有待分析文档"""
    files = []
    for ext in DOC_EXTENSIONS:
        files.extend(doc_dir.glob(f"*{ext}"))
    return sorted([f for f in files if f.is_file()])


def _load_api_key(api_key: str | None) -> str | None:
    """获取 API Key：优先 --api-key，其次 .env，最后环境变量"""
    if api_key:
        return api_key
    try:
        from dotenv import load_dotenv
        for search_dir in [Path.cwd(), Path(__file__).resolve().parent.parent]:
            env_path = search_dir / ".env"
            if env_path.exists():
                load_dotenv(env_path)
                break
        else:
            load_dotenv()
    except ImportError:
        pass
    return os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")


def _get_genai_model(model_name: str, api_key: str | None):
    """获取配置好的 genai 模型"""
    api_key = _load_api_key(api_key)
    if not api_key:
        raise ValueError(
            "未配置 API Key。请在 .env 中设置 GEMINI_API_KEY 或 GOOGLE_API_KEY，"
            "或通过 --api-key 传入，或设置环境变量"
        )
    try:
        import google.generativeai as genai
    except ImportError:
        raise ImportError("请安装 google-generativeai: pip install google-generativeai")
    genai.configure(api_key=api_key)
    return genai.GenerativeModel(model_name), genai


def _call_llm(
    prompt: str,
    model_name: str,
    api_key: str | None = None,
    *,
    max_retries: int = 3,
    log=None,
) -> str:
    """调用大模型 API（纯文本），含网络错误重试"""
    log = log or (lambda x: None)
    model, _ = _get_genai_model(model_name, api_key)
    max_chars = 900_000
    if len(prompt) > max_chars:
        prompt = prompt[:max_chars] + "\n\n[文档过长已截断]"
    last_err = None
    for attempt in range(max_retries):
        try:
            response = model.generate_content(prompt)
            return response.text if response.text else ""
        except RETRY_EXCEPTIONS as e:
            last_err = e
            if attempt < max_retries - 1:
                wait = (attempt + 1) * 10
                log(f"      ⚠ 网络错误，{wait}s 后重试 ({attempt + 2}/{max_retries}): {type(e).__name__}")
                time.sleep(wait)
        except Exception:
            raise
    raise RuntimeError(f"API 调用失败（已重试{max_retries}次）: {last_err}") from last_err


def _call_llm_with_file(
    prompt: str,
    file_path: Path,
    mime_type: str,
    model_name: str,
    api_key: str | None = None,
    *,
    max_retries: int = 3,
    log=None,
) -> str:
    """调用大模型 API（多模态：PDF、图片），含网络错误重试"""
    log = log or (lambda x: None)
    model, genai = _get_genai_model(model_name, api_key)
    last_err = None
    for attempt in range(max_retries):
        try:
            uploaded = genai.upload_file(path=str(file_path.resolve()), mime_type=mime_type)
            response = model.generate_content([prompt, uploaded])
            return response.text if response.text else ""
        except RETRY_EXCEPTIONS as e:
            last_err = e
            if attempt < max_retries - 1:
                wait = (attempt + 1) * 15
                log(f"      ⚠ 上传/网络错误，{wait}s 后重试 ({attempt + 2}/{max_retries}): {type(e).__name__}")
                time.sleep(wait)
        except Exception as e:
            raise RuntimeError(f"上传/分析文件失败 {file_path.name}: {e}") from e
    raise RuntimeError(f"上传文件失败（已重试{max_retries}次） {file_path.name}: {last_err}") from last_err


def _agent1_analyze(
    content: str | None,
    file_path: Path | None,
    mime_type: str | None,
    model_name: str,
    api_key: str | None,
    log=None,
) -> str:
    """Agent1：一级规范分析（支持文本或多模态文件）"""
    if file_path and mime_type:
        prompt = AGENT1_LEVEL1_PROMPT + "\n\n请分析下方文档/图片。"
        return _call_llm_with_file(prompt, file_path, mime_type, model_name, api_key, log=log)
    prompt = AGENT1_LEVEL1_PROMPT + "\n\n" + (content or "")[:120_000]
    return _call_llm(prompt, model_name, api_key, log=log)


def _agent2_analyze(
    content: str | None,
    file_path: Path | None,
    mime_type: str | None,
    model_name: str,
    api_key: str | None,
    log=None,
) -> str:
    """Agent2：二级元语义分析（支持文本或多模态文件）"""
    if file_path and mime_type:
        prompt = AGENT2_LEVEL2_PROMPT + "\n\n请分析下方文档/图片。"
        return _call_llm_with_file(prompt, file_path, mime_type, model_name, api_key, log=log)
    prompt = AGENT2_LEVEL2_PROMPT + "\n\n" + (content or "")[:120_000]
    return _call_llm(prompt, model_name, api_key, log=log)


def _agent3_review(
    source: str | None,
    file_path: Path | None,
    mime_type: str | None,
    level1: str,
    level2: str,
    model_name: str,
    api_key: str | None,
    log=None,
) -> str:
    """Agent3：写作质量评审（支持文本或多模态源文档）"""
    if file_path and mime_type:
        prompt = AGENT3_REVIEW_PROMPT.format(
            source_content="[源文档为多模态文件，已随请求一并传入，请结合其内容进行评审]",
            level1_content=level1[:60_000],
            level2_content=level2[:60_000],
        )
        return _call_llm_with_file(prompt, file_path, mime_type, model_name, api_key, log=log)
    prompt = AGENT3_REVIEW_PROMPT.format(
        source_content=(source or "")[:80_000],
        level1_content=level1[:60_000],
        level2_content=level2[:60_000],
    )
    return _call_llm(prompt, model_name, api_key, log=log)


def analyze_single_doc(
    doc_path: Path,
    model_name: str,
    api_key: str | None = None,
    *,
    delay: float = 1.0,
    log=None,
) -> DocAnalysisResult:
    """对单文档进行三智能体分析（支持文本、Word、PDF、图片）"""
    log = log or (lambda x: None)
    is_mm = _is_multimodal(doc_path)
    mime = _get_mime_type(doc_path) if is_mm else None
    file_path = doc_path if is_mm else None
    content = "" if is_mm else _read_doc(doc_path)

    if not is_mm:
        if not content.strip() or content.startswith("["):
            log(f"      ⚠ 跳过：文档无法读取或为空")
            return DocAnalysisResult(
                doc_path=doc_path,
                level1=f"# 分析跳过\n文档无法读取或为空: {doc_path.name}",
                level2=f"# 分析跳过\n文档无法读取或为空: {doc_path.name}",
            )
        full_content = content[:120_000]
        if len(content) > 120_000:
            full_content += "\n\n[文档已截断，仅分析前 12 万字]"
    else:
        full_content = None

    t0 = time.time()
    log(f"      → Agent1 一级规范分析...")
    level1 = _agent1_analyze(full_content, file_path, mime, model_name, api_key, log=log)
    log(f"      ✓ Agent1 完成 ({time.time()-t0:.1f}s)")
    time.sleep(delay)

    t1 = time.time()
    log(f"      → Agent2 二级元语义分析...")
    level2 = _agent2_analyze(full_content, file_path, mime, model_name, api_key, log=log)
    log(f"      ✓ Agent2 完成 ({time.time()-t1:.1f}s)")
    time.sleep(delay)

    t2 = time.time()
    log(f"      → Agent3 写作质量评审...")
    review = _agent3_review(
        full_content, file_path, mime, level1, level2, model_name, api_key, log=log
    )
    log(f"      ✓ Agent3 完成 ({time.time()-t2:.1f}s)，本文档共 {time.time()-t0:.1f}s")

    scores, weighted = _parse_review_scores(review)

    return DocAnalysisResult(
        doc_path=doc_path,
        level1=level1,
        level2=level2,
        review=review,
        scores=scores,
        weighted_score=weighted,
    )


def _write_score_file(out_path: Path, result: DocAnalysisResult) -> None:
    """写入单文档评分文件"""
    lines = [
        f"# {result.doc_path.name} 写作质量评审",
        "",
        "## 各维度评分",
        "",
    ]
    for name, w in REVIEW_DIMENSIONS:
        s = result.scores.get(name, 0)
        lines.append(f"- **{name}**（权重{w*100:.0f}%）：{s} 分")
    lines.append("")
    lines.append(f"## 综合评分\n\n**{result.weighted_score} / 5**（加权平均，四舍五入至 0.5）")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 完整评审内容")
    lines.append("")
    lines.append(result.review)
    out_path.write_text("\n".join(lines), encoding="utf-8")


# 表格列简短名
_DIM_ABBREV = ["事实", "来源", "深度", "客观", "全面", "时效", "清晰", "洞察"]


def _write_ranking_table(out_path: Path, results: list[DocAnalysisResult]) -> None:
    """生成评分排序表格"""
    sorted_results = sorted(results, key=lambda r: r.weighted_score, reverse=True)
    abbrevs = _DIM_ABBREV[: len(REVIEW_DIMENSIONS)]

    header = "| 排名 | 文档名 | " + " | ".join(abbrevs) + " | 综合分 |"
    sep = "|" + "|".join(["---"] * (len(REVIEW_DIMENSIONS) + 3)) + "|"

    rows = []
    for i, r in enumerate(sorted_results, 1):
        scores_str = " | ".join(str(r.scores.get(d[0], "-")) for d in REVIEW_DIMENSIONS)
        rows.append(f"| {i} | {r.doc_path.name} | {scores_str} | **{r.weighted_score}** |")

    content = [
        "# 写作质量评分排序表",
        "",
        "按综合评分降序排列。",
        "",
        header,
        sep,
        *rows,
        "",
    ]
    out_path.write_text("\n".join(content), encoding="utf-8")


def run_aggregation(
    level1_texts: list[str],
    level2_texts: list[str],
    score_summary: str,
    model_name: str,
    api_key: str | None = None,
    log=None,
) -> str:
    """汇总归纳（融入评分）"""
    l1_merged = "\n\n---\n\n".join(f"## 文档 {i+1}\n{t}" for i, t in enumerate(level1_texts))
    l2_merged = "\n\n---\n\n".join(f"## 文档 {i+1}\n{t}" for i, t in enumerate(level2_texts))
    max_len = 100_000
    if len(l1_merged) > max_len:
        l1_merged = l1_merged[:max_len] + "\n\n[已截断]"
    if len(l2_merged) > max_len:
        l2_merged = l2_merged[:max_len] + "\n\n[已截断]"

    prompt = SUMMARY_PROMPT.format(
        level1_texts=l1_merged,
        level2_texts=l2_merged,
        score_summary=score_summary,
    )
    return _call_llm(prompt, model_name, api_key, log=log)


def run_skill_conversion(
    summary_text: str, model_name: str, api_key: str | None = None, log=None
) -> str:
    """将汇总分析转换为 Skill 内容"""
    prompt = SKILL_CONVERSION_PROMPT.format(summary_text=summary_text[:80_000])
    return _call_llm(prompt, model_name, api_key, log=log)


def analyze_doc_dir(
    doc_dir: Path,
    model_name: str,
    api_key: str | None = None,
    *,
    output_in_place: bool = True,
    delay: float = 1.0,
    resume: bool = False,
    log=None,
) -> Path:
    """
    分析目录下所有文档：Agent1/Agent2/Agent3 → Level1/Level2/评分 → 汇总 → Skill
    """
    log = log or (lambda x: None)
    doc_dir = doc_dir.resolve()
    if not doc_dir.is_dir():
        raise NotADirectoryError(f"不是有效目录: {doc_dir}")

    out_dir = doc_dir / "_analysis"
    out_dir.mkdir(exist_ok=True)
    (out_dir / "level1").mkdir(exist_ok=True)
    (out_dir / "level2").mkdir(exist_ok=True)
    (out_dir / "scores").mkdir(exist_ok=True)

    docs = _get_doc_files(doc_dir)
    if not docs:
        raise FileNotFoundError(
            f"目录下未找到可分析文档（支持: {', '.join(DOC_EXTENSIONS)}）: {doc_dir}"
        )

    log(f"找到 {len(docs)} 个文档，三智能体分析开始...")

    results: list[DocAnalysisResult] = []
    for i, doc in enumerate(docs, 1):
        base = doc.stem
        l1_path = out_dir / "level1" / f"{base}_L1.md"
        l2_path = out_dir / "level2" / f"{base}_L2.md"
        score_path = out_dir / "scores" / f"{base}_score.md"

        if resume and l1_path.exists() and l2_path.exists() and score_path.exists():
            log(f"  [{i}/{len(docs)}] {doc.name} (跳过，已存在)")
            score_txt = score_path.read_text(encoding="utf-8")
            scores_map, w = _parse_review_scores(score_txt)
            m = re.search(r"\*\*([\d.]+)\s*/\s*5\*\*", score_txt)
            w = float(m.group(1)) if m else w
            res = DocAnalysisResult(
                doc_path=doc,
                level1=l1_path.read_text(encoding="utf-8"),
                level2=l2_path.read_text(encoding="utf-8"),
                review="",
                scores=scores_map,
                weighted_score=w,
            )
        else:
            log(f"  [{i}/{len(docs)}] {doc.name}")
            res = analyze_single_doc(doc, model_name, api_key, delay=delay, log=log)
            l1_path.write_text(res.level1, encoding="utf-8")
            l2_path.write_text(res.level2, encoding="utf-8")
            _write_score_file(score_path, res)
        results.append(res)

    _write_ranking_table(out_dir / "scores" / "ranking.md", results)

    level1_texts = [r.level1 for r in results if not r.level1.startswith("# 分析跳过")]
    level2_texts = [r.level2 for r in results if not r.level2.startswith("# 分析跳过")]
    score_summary_lines = []
    for r in sorted(results, key=lambda x: x.weighted_score, reverse=True):
        dims = " | ".join(str(r.scores.get(d[0], "-")) for d in REVIEW_DIMENSIONS)
        score_summary_lines.append(f"- {r.doc_path.name}: {dims} | 综合 {r.weighted_score}")

    score_summary = "\n".join(score_summary_lines)

    log("正在汇总归纳（融入评分，重点学习高分文档）...")
    if not level1_texts or not level2_texts:
        log("警告: 无有效分析结果，跳过汇总")
        summary = "# 汇总跳过\n无有效 Level1/Level2 分析结果。"
    else:
        summary = run_aggregation(
            level1_texts, level2_texts, score_summary, model_name, api_key, log=log
        )

    (out_dir / "summary.md").write_text(summary, encoding="utf-8")

    log("正在生成 Skill 文件...")
    skill_content = run_skill_conversion(summary, model_name, api_key, log=log)
    (out_dir / "SKILL.md").write_text(skill_content, encoding="utf-8")

    log(f"完成，输出目录: {out_dir}")
    return out_dir
