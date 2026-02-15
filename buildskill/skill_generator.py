"""
Skill 文件生成模块
将项目分析结果转换为 Cursor Skill 格式的 SKILL.md
"""

import re
from pathlib import Path
from .analyzer import ProjectAnalysis


def _sanitize_skill_name(name: str) -> str:
    """
    将项目名转换为合法的 skill name
    规则: 小写、仅字母数字和连字符、最多 64 字符
    """
    s = re.sub(r"[^a-z0-9\-]", "-", name.lower())
    s = re.sub(r"-+", "-", s).strip("-")
    return s[:64] or "unnamed-skill"


def _sanitize_description(desc: str, max_len: int = 1024) -> str:
    """清理描述，确保符合 Skill 要求"""
    # 移除多余空白和换行
    desc = " ".join(desc.split())
    # 截断
    return desc[:max_len].strip()


def generate_skill_md(analysis: ProjectAnalysis) -> str:
    """
    根据分析结果生成 SKILL.md 内容

    Args:
        analysis: 项目分析结果

    Returns:
        SKILL.md 的完整内容
    """
    skill_name = _sanitize_skill_name(analysis.name)
    description = _sanitize_description(
        analysis.description
        or f"Provides capabilities from {analysis.name}. "
        f"Use when working with {', '.join(analysis.triggers[:5]) or skill_name}."
    )

    sections = []

    # YAML frontmatter
    frontmatter = f"""---
name: {skill_name}
description: {description}
---
"""
    sections.append(frontmatter)

    # 标题
    title = analysis.name.replace("-", " ").replace("_", " ").title()
    sections.append(f"# {title}\n")

    # 项目概述
    if analysis.description:
        sections.append("## Overview\n")
        sections.append(f"{analysis.description}\n")

    # 技术栈
    if analysis.tech_stack:
        sections.append("## Tech Stack\n")
        sections.append(", ".join(analysis.tech_stack) + "\n")

    # 使用说明
    if analysis.instructions:
        sections.append("## Instructions\n")
        for instr in analysis.instructions[:20]:
            sections.append(f"{instr}\n")
        sections.append("")

    # 示例
    if analysis.examples:
        sections.append("## Examples\n")
        for i, ex in enumerate(analysis.examples[:5], 1):
            sections.append(f"### Example {i}\n")
            sections.append(f"```\n{ex[:800]}\n```\n\n")

    # 提示词参考
    if analysis.prompts:
        sections.append("## Prompt Reference\n")
        sections.append(
            "The following prompts are used in this project:\n\n"
        )
        for i, prompt in enumerate(analysis.prompts[:5], 1):
            sections.append(f"**Prompt {i}:**\n")
            sections.append(f"```\n{prompt}\n```\n\n")

    # 关键文件
    if analysis.key_files:
        sections.append("## Key Files\n")
        for f in analysis.key_files[:15]:
            sections.append(f"- `{f}`\n")
        sections.append("")

    # 配置摘要
    if analysis.config_summary:
        sections.append("## Configuration\n")
        for config_name, config_data in list(analysis.config_summary.items())[:3]:
            sections.append(f"### {config_name}\n")
            if isinstance(config_data, dict):
                for k, v in config_data.items():
                    if v:
                        sections.append(f"- **{k}**: {v}\n")
            sections.append("")

    return "\n".join(sections)


def write_skill_file(
    analysis: ProjectAnalysis,
    output_dir: Path,
    *,
    skill_name: str | None = None,
) -> Path:
    """
    将 Skill 写入文件

    Args:
        analysis: 项目分析结果
        output_dir: 输出目录，会创建 skill-name 子目录
        skill_name: 可选，覆盖自动生成的 skill 名称

    Returns:
        生成的 SKILL.md 路径
    """
    name = skill_name or _sanitize_skill_name(analysis.name)
    skill_dir = output_dir / name
    skill_dir.mkdir(parents=True, exist_ok=True)

    content = generate_skill_md(analysis)
    skill_file = skill_dir / "SKILL.md"
    skill_file.write_text(content, encoding="utf-8")

    return skill_file
