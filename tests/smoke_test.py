from pathlib import Path
import ast
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main() -> None:
    python_files = [p for p in ROOT.rglob("*.py") if ".venv" not in p.parts]
    for path in python_files:
        ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

    import main as app_main  # noqa: F401
    import server
    from signals import list_calculators

    strategies = list_calculators()
    assert len(strategies) == 20, f"预期20个策略，实际{len(strategies)}"
    assert server.health()["status"] == "ok"
    assert (ROOT / "terminal" / "package.json").exists()
    assert (ROOT / "stock_trading" / "__init__.py").exists()
    print(f"PASS: {len(python_files)}个Python文件语法正确，20个策略已注册，API健康检查通过。")


if __name__ == "__main__":
    main()
