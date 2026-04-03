"""One-off helper: insert doc links into README.md (UTF-8). Run from repo root."""
from __future__ import annotations

from pathlib import Path


def main() -> None:
    root = Path(__file__).resolve().parent.parent
    readme = root / "README.md"
    text = readme.read_text(encoding="utf-8")

    block_env = """## Окружение и воспроизводимость

- **Python:** 3.11–3.13; в продакшене зафиксируйте минорную версию на хосте и в CI.
- **Полная установка:** `pip install -r requirements.txt` (включая `rembg` и `onnxruntime`).
- **Тесты и скрипты без полного стека:** `pip install -r requirements-dev.txt` (добавлен `scikit-image` для batch-скрипта по умолчанию).
- Подробности: [docs/ENVIRONMENT.md](docs/ENVIRONMENT.md).

"""
    if "## Окружение и воспроизводимость" not in text:
        text = text.replace("## Переменные окружения\n", block_env + "## Переменные окружения\n", 1)

    policy_line = "- Политика хранения и расписание: [docs/OUTPUTS_POLICY.md](docs/OUTPUTS_POLICY.md).\n"
    if "OUTPUTS_POLICY.md" not in text and "## Политика хранения outputs" in text:
        text = text.replace(
            "## Политика хранения outputs\n\n- Для ручной очистки старых файлов:\n",
            "## Политика хранения outputs\n\n"
            + policy_line
            + "\n- Для ручной очистки старых файлов:\n",
            1,
        )

    int_line = "\nИнтеграция клиента (коды ответов, `--strict`): [docs/INTEGRATION.md](docs/INTEGRATION.md).\n"
    if "INTEGRATION.md" not in text and "## Интеграционный smoke" in text:
        text = text.replace(
            "## Интеграционный smoke\n\nБыстрый прогон",
            "## Интеграционный smoke" + int_line + "\nБыстрый прогон",
            1,
        )

    backlog_line = "\nПриоритизированный backlog: [docs/BACKLOG.md](docs/BACKLOG.md).\n"
    if "BACKLOG.md" not in text:
        text = text.rstrip() + backlog_line + "\n"

    batch_help = (
        "\nСвой каталог изображений: "
        "`python scripts/real_batch_run.py --image-dir \"D:/photos\" --all-in-dir --count 12`. "
        "Отчёт JSON содержит поля `meta` и `rows`. QA-заметки: [reports/qa_notes.md](reports/qa_notes.md).\n"
    )
    if "--all-in-dir" not in text and "Batch-прогон" in text:
        text = text.replace(
            "Результаты: `reports/real_batch_report.md` и `reports/real_batch_report.json`.",
            "Результаты: `reports/real_batch_report.md` и `reports/real_batch_report.json`."
            + batch_help,
            1,
        )

    readme.write_text(text, encoding="utf-8")
    print("README.md updated")


if __name__ == "__main__":
    main()
