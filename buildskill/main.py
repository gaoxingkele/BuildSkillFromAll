"""
buildskill 主入口
支持：1) GitHub 仓库 → Skill；2) 文档目录 → 元知识分析 → Skill
"""

import argparse
import sys
from pathlib import Path

from .cloner import clone_repo, parse_github_url
from .analyzer import analyze_repo
from .skill_generator import write_skill_file
from .prompt_library import find_prompt_files, generate_prompt_library_skills
from .doc_analyzer import analyze_doc_dir


def cmd_repo(args: argparse.Namespace, log) -> int:
    """仓库模式：克隆、分析、生成 Skill"""
    project_root = Path(__file__).resolve().parent.parent
    git_dir = args.git_dir or project_root / "git"
    output_dir = args.output or project_root / "output"

    log("")
    log("=" * 50)
    log("  buildskill repo 开始")
    log("=" * 50)
    log("")

    if args.from_path:
        repo_path = args.from_path.resolve()
        if not repo_path.exists():
            print(f"错误: 路径不存在: {repo_path}", file=sys.stderr)
            return 1
        log(f"使用本地路径: {repo_path}")
    else:
        log("正在克隆仓库...")
        git_dir.mkdir(parents=True, exist_ok=True)
        repo_path = clone_repo(
            args.repo,
            git_dir,
            force=args.force,
            depth=None if args.full_clone else 1,
            log=log,
        )
        log(f"  已克隆到: {repo_path}")

    if args.prompt_library:
        log("正在扫描提示词文件...")
        prompts = find_prompt_files(repo_path)
        log(f"  找到 {len(prompts)} 个提示词")
        if not prompts:
            print("错误: 未找到提示词文件", file=sys.stderr)
            return 1
        log("正在为每个提示词生成 Skill...")
        skill_paths = generate_prompt_library_skills(repo_path, output_dir)
        for i, p in enumerate(skill_paths[:5], 1):
            log(f"  [{i}] {p.relative_to(output_dir)}")
        if len(skill_paths) > 5:
            log(f"  ... 及另外 {len(skill_paths) - 5} 个")
        print(f"\n完成! 共生成 {len(skill_paths)} 个 Skill，输出目录: {output_dir}")
        return 0

    log("正在分析代码和配置...")
    analysis = analyze_repo(repo_path)
    log(f"  项目: {analysis.name}")
    log("正在生成 Skill 文件...")
    output_dir.mkdir(parents=True, exist_ok=True)
    skill_path = write_skill_file(analysis, output_dir)
    log(f"  已生成: {skill_path}")
    print(f"\n完成! Skill 文件: {skill_path}")
    return 0


def _format_error(e: Exception) -> str:
    """将异常转为用户可读的错误提示"""
    err = str(e)
    if "API key" in err.lower() or "API Key" in err:
        return (
            f"【API Key 配置错误】{e}\n"
            "  → 请在 .env 中设置 GEMINI_API_KEY，或通过 --api-key 传入"
        )
    if "403" in err or "PermissionDenied" in str(type(e).__name__) or "leaked" in err.lower():
        return (
            f"【API Key 无效】{e}\n"
            "  → Key 可能已泄露或过期，请在 Google AI Studio 生成新 Key"
        )
    if "SSL" in str(e) or "SSLError" in str(type(e).__name__):
        return (
            f"【网络/SSL 错误】{e}\n"
            "  → 多为瞬时问题，可使用 --resume 续跑；检查网络/代理"
        )
    if "上传" in err or "upload" in err.lower():
        return (
            f"【文件上传失败】{e}\n"
            "  → 检查网络；大文件可稍后使用 --resume 重试"
        )
    if "未找到" in err or "FileNotFound" in str(type(e).__name__):
        return f"【文件/目录错误】{e}"
    return str(e)


def cmd_analyze(args: argparse.Namespace, log) -> int:
    """文档分析模式：Level1/Level2 分析 → 汇总 → Skill"""
    doc_dir = args.doc_dir.resolve()
    if not doc_dir.is_dir():
        print(f"错误: 不是有效目录: {doc_dir}", file=sys.stderr)
        return 1
    try:
        log("")
        log("=" * 50)
        log("  buildskill analyze 开始")
        log(f"  文档目录: {doc_dir}")
        log(f"  模型: {args.model}")
        log("=" * 50)
        log("")
        out_dir = analyze_doc_dir(
            doc_dir,
            model_name=args.model,
            api_key=args.api_key,
            delay=args.delay,
            resume=getattr(args, "resume", False),
            log=log,
        )
        log("")
        log("=" * 50)
        print(f"\n完成! 输出目录: {out_dir}")
        print(f"  - level1/    Agent1 一级规范分析")
        print(f"  - level2/    Agent2 二级元语义分析")
        print(f"  - scores/    Agent3 评审得分与排序表")
        print(f"  - summary.md 汇总归纳（融入评分）")
        print(f"  - SKILL.md   写作指导 Skill")
        return 0
    except FileNotFoundError as e:
        print(f"\n错误: {_format_error(e)}", file=sys.stderr)
        return 1
    except ValueError as e:
        print(f"\n错误: {_format_error(e)}", file=sys.stderr)
        return 1
    except RuntimeError as e:
        print(f"\n错误: {_format_error(e)}", file=sys.stderr)
        return 1


def main() -> int:
    # 根据首个参数判断模式，以兼容 buildskill owner/repo 旧用法
    argv = sys.argv[1:]
    pos_args = [a for a in argv if not a.startswith("-")]
    if pos_args and pos_args[0] == "analyze":
        # 文档分析模式
        ap = argparse.ArgumentParser(
            description="文档元知识分析 → Skill",
            epilog="示例: buildskill analyze ./docs -m gemini-2.5-pro",
        )
        ap.add_argument("analyze", nargs="?", help="(子命令)")
        ap.add_argument("doc_dir", type=Path, nargs="?", help="文档目录")
        ap.add_argument("-q", "--quiet", action="store_true")
        ap.add_argument("-m", "--model", default="gemini-2.5-pro", help="大模型名称（默认 gemini-2.5-pro，支持多模态）")
        ap.add_argument("--api-key", default=None, help="API Key")
        ap.add_argument("--delay", type=float, default=1.0)
        ap.add_argument("--resume", action="store_true", help="跳过已完成的文档，仅处理未完成的")
        args = ap.parse_args()
        args.command = "analyze"
        doc_dir = getattr(args, "doc_dir", None)
        if not doc_dir or not Path(doc_dir).resolve().exists():
            print("错误: 请指定有效的文档目录，如 buildskill analyze ./docs", file=sys.stderr)
            return 1
    else:
        # 仓库模式（含 buildskill owner/repo 兼容）
        rp = argparse.ArgumentParser(
            description="buildskill: GitHub 仓库/文档目录 → Cursor Skill",
            epilog="示例: buildskill owner/repo  |  buildskill repo owner/repo --prompt-library",
        )
        rp.add_argument("repo", nargs="?", help="GitHub URL 或 owner/repo")
        rp.add_argument("-q", "--quiet", action="store_true")
        rp.add_argument("-o", "--output", type=Path)
        rp.add_argument("-g", "--git-dir", type=Path)
        rp.add_argument("-f", "--force", action="store_true")
        rp.add_argument("--full-clone", action="store_true")
        rp.add_argument("--prompt-library", action="store_true")
        rp.add_argument("--from-path", type=Path)
        args = rp.parse_args()
        args.command = "repo"

    def log(msg: str) -> None:
        if not getattr(args, "quiet", False):
            print(msg)

    try:
        if args.command == "repo":
            if not args.from_path and (not args.repo or not parse_github_url(args.repo)):
                print("错误: 请提供有效 GitHub 地址，或使用 --from-path", file=sys.stderr)
                return 1
            return cmd_repo(args, log)
        if args.command == "analyze":
            return cmd_analyze(args, log)
        return 0
    except FileExistsError as e:
        print(f"\n错误: 【目录已存在】{e}", file=sys.stderr)
        return 1
    except FileNotFoundError as e:
        print(f"\n错误: {_format_error(e)}", file=sys.stderr)
        return 1
    except PermissionError as e:
        print(f"\n错误: 【权限/认证】{e}", file=sys.stderr)
        return 1
    except ValueError as e:
        print(f"\n错误: {_format_error(e)}", file=sys.stderr)
        return 1
    except RuntimeError as e:
        print(f"\n错误: {_format_error(e)}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"\n错误: {_format_error(e)}", file=sys.stderr)
        if not getattr(args, "quiet", False):
            import traceback
            traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
