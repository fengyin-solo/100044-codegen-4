"""内存数据仓库：给每个业务模块准备一份可筛选、可流转的示例数据。

真实项目里这里会换成数据库访问层；当前实现只依赖标准库，保证克隆下来就能起。
"""
from __future__ import annotations

from datetime import date
from typing import Any

from app.seed import SEED_ROWS


class Store:
    def __init__(self) -> None:
        self._tables: dict[str, list[dict[str, Any]]] = {
            name: [dict(row) for row in rows] for name, rows in SEED_ROWS.items()
        }

    def sync_staff_flags(self) -> None:
        """员工档案的汇总标记按现算资格回填。

        资格口径本身不落库（读取时现算），这里只把看板/概览要用的
        status/pending/abnormal 同步成与资格口径一致，避免两处口径漂移。
        需在模块级 ``store`` 就绪后再调用，避免与 training 服务互相导入。
        """
        from app.services.training import QUALIFIED_VALID, TrainingService

        service = TrainingService()
        for row in self._tables.get("staff", []):
            enriched = service.enrich(row, today=date.today())
            row["status"] = enriched["资格口径"]
            row["pending"] = enriched["资格口径"] != QUALIFIED_VALID
            row["abnormal"] = not enriched["持证上岗"]

    def module_names(self) -> list[str]:
        return sorted(self._tables)

    def rows(self, module: str) -> list[dict[str, Any]]:
        return self._tables.setdefault(module, [])

    def find(self, module: str, entry_id: int) -> dict[str, Any] | None:
        for row in self.rows(module):
            if int(row.get("id", 0)) == entry_id:
                return row
        return None

    def overview(self) -> dict[str, object]:
        from app.services.training import QUALIFIED_VALID, TrainingService

        training = TrainingService()
        modules: list[dict[str, object]] = []
        for name in self.module_names():
            rows = self.rows(name)
            if name == "staff":
                # 员工资格口径随当天日期与岗位阈值变化，概览也现算，避免与列表口径漂移。
                calibers = [training.enrich(row) for row in rows]
                modules.append({
                    "name": name,
                    "created": len(rows),
                    "pending": sum(1 for row in calibers if row["资格口径"] != QUALIFIED_VALID),
                    "abnormal": sum(1 for row in calibers if not row["持证上岗"]),
                })
                continue
            modules.append({
                "name": name,
                "created": len(rows),
                "pending": sum(1 for row in rows if row.get("pending")),
                "abnormal": sum(1 for row in rows if row.get("abnormal")),
            })
        cards = [
            {"label": "业务模块", "value": len(modules)},
            {"label": "今日新增", "value": sum(int(item["created"]) for item in modules)},
            {"label": "待处理", "value": sum(int(item["pending"]) for item in modules)},
            {"label": "异常量", "value": sum(int(item["abnormal"]) for item in modules)},
        ]
        return {"cards": cards, "modules": modules}


store = Store()
store.sync_staff_flags()
