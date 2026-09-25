"""员工培训与持证上岗业务规则：岗位规则、证书状态口径、批量导入校验都收在这里。"""
from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from typing import Any

from app.store import store

MODULE = "training"

# 岗位规则：每个岗位要求持有的证书、到期提醒阈值（天）与必训课程。
POSITION_RULES: dict[str, dict[str, Any]] = {
    "运行工": {"必备证书": ["污水处理工证"], "提醒阈值天数": 30, "必训课程": ["安全操作规程", "工艺运行培训"]},
    "化验员": {"必备证书": ["化验员上岗证"], "提醒阈值天数": 30, "必训课程": ["化验安全培训"]},
    "电工": {"必备证书": ["低压电工证"], "提醒阈值天数": 60, "必训课程": ["电气安全培训"]},
    "受限空间监护人": {"必备证书": ["受限空间监护证"], "提醒阈值天数": 30, "必训课程": ["受限空间应急演练"]},
}
DEFAULT_REMIND_DAYS = 30

# 资格状态口径：到期当天仍算当日有效（可上岗），超期才失去上岗资格。
QUALIFICATION_STATUSES = ["持证有效", "临期提醒", "今日到期", "已超期", "证书缺失"]
SEVERITY = {"持证有效": 0, "临期提醒": 1, "今日到期": 2, "已超期": 3, "证书缺失": 4}
QUALIFIED_STATUSES = {"持证有效", "临期提醒", "今日到期"}

DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
IMPORT_COLUMNS = ["员工编号", "姓名", "岗位", "证书名称", "证书编号", "有效期至"]


def parse_date(value: object) -> date | None:
    """只接受 YYYY-MM-DD 且必须是真实存在的日期，其他一律视为不合法。"""
    text = str(value or "").strip()
    if not DATE_PATTERN.match(text):
        return None
    try:
        return datetime.strptime(text, "%Y-%m-%d").date()
    except ValueError:
        return None


def cert_state(expiry: date, today: date, remind_days: int) -> str:
    """单张证书的状态口径：超期、到期当天、阈值内临期、阈值外有效。"""
    days = (expiry - today).days
    if days < 0:
        return "已超期"
    if days == 0:
        return "今日到期"
    if days <= remind_days:
        return "临期提醒"
    return "持证有效"


class TrainingService:
    def __init__(self) -> None:
        # 启动时先刷一遍派生状态，保证概览看板与列表口径一致。
        self._refresh_all()

    def list_entries(
        self,
        *,
        keyword: str | None = None,
        status: str | None = None,
        position: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        today = date.today()
        rows = [self._refresh(row, today) for row in store.rows(MODULE)]
        if keyword:
            rows = [
                row for row in rows
                if keyword in str(row.get("员工编号", "")) or keyword in str(row.get("姓名", ""))
            ]
        if position:
            rows = [row for row in rows if row.get("岗位") == position]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        total = len(rows)
        start = max(page - 1, 0) * size
        return rows[start:start + size], total

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        row = store.find(MODULE, entry_id)
        return self._refresh(row) if row is not None else None

    def list_rules(self) -> list[dict[str, Any]]:
        return [{"岗位": position, **rule} for position, rule in POSITION_RULES.items()]

    def list_reminders(self) -> list[dict[str, Any]]:
        """证书到期提醒：剩余天数落在岗位阈值内（含到期当天）的必备证书。"""
        today = date.today()
        items: list[dict[str, Any]] = []
        for row in store.rows(MODULE):
            self._refresh(row, today)
            rule = POSITION_RULES.get(str(row.get("岗位", "")), {})
            threshold = int(rule.get("提醒阈值天数", DEFAULT_REMIND_DAYS))
            required = rule.get("必备证书", [])
            for cert in row.get("证书列表", []):
                if cert.get("证书名称") not in required:
                    continue
                days = cert.get("剩余天数")
                if days is None or not 0 <= int(days) <= threshold:
                    continue
                items.append({
                    "员工编号": row.get("员工编号", ""),
                    "姓名": row.get("姓名", ""),
                    "岗位": row.get("岗位", ""),
                    "证书名称": cert.get("证书名称", ""),
                    "有效期至": cert.get("有效期至", ""),
                    "剩余天数": days,
                    "提醒等级": "今日到期" if int(days) == 0 else "临期提醒",
                })
        items.sort(key=lambda item: int(item["剩余天数"]))
        return items

    def qualification_stats(self) -> dict[str, int]:
        counts = {status: 0 for status in QUALIFICATION_STATUSES}
        for row in store.rows(MODULE):
            counts[str(self._refresh(row)["资格状态"])] += 1
        return counts

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        normalized = {key: str(values.get(key) or "").strip() for key in IMPORT_COLUMNS}
        reasons = self._validate_row(normalized, existing=self._existing_codes(), batch_seen=set())
        if reasons:
            return None, reasons
        return self._build_entry(normalized), []

    def import_entries(self, lines: list[str]) -> dict[str, Any]:
        """批量导入：逐行校验并给出原因，合法行落库，重复人员只拒绝不覆盖。"""
        existing = self._existing_codes()
        batch_seen: set[str] = set()
        results: list[dict[str, Any]] = []
        imported = 0
        for index, raw in enumerate(lines, start=1):
            line = str(raw).strip()
            if not line:
                continue
            parts = [part.strip() for part in line.replace("，", ",").split(",")]
            if len(parts) != len(IMPORT_COLUMNS):
                results.append({
                    "行号": index,
                    "员工编号": parts[0] if parts else "",
                    "ok": False,
                    "原因": f"应为 {len(IMPORT_COLUMNS)} 列（{'，'.join(IMPORT_COLUMNS)}），实际 {len(parts)} 列",
                })
                continue
            values = dict(zip(IMPORT_COLUMNS, parts))
            reasons = self._validate_row(values, existing=existing, batch_seen=batch_seen)
            if reasons:
                results.append({"行号": index, "员工编号": values["员工编号"], "ok": False, "原因": "；".join(reasons)})
                continue
            self._build_entry(values)
            existing.add(values["员工编号"])
            batch_seen.add(values["员工编号"])
            imported += 1
            results.append({"行号": index, "员工编号": values["员工编号"], "ok": True, "原因": ""})
        failed = sum(1 for item in results if not item["ok"])
        return {
            "ok": failed == 0 and imported > 0,
            "message": f"导入完成：成功 {imported} 条，失败 {failed} 条",
            "total": len(results),
            "imported": imported,
            "failed": failed,
            "results": results,
        }

    def run_action(self, entry_id: int, action: str) -> tuple[dict[str, Any] | None, str]:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"员工档案 {entry_id} 不存在或已归档"
        if action == "生成培训计划":
            rule = POSITION_RULES.get(str(entry.get("岗位", "")))
            if rule is None:
                return None, f"岗位「{entry.get('岗位', '')}」未配置岗位规则，无法生成培训计划"
            plans = entry.setdefault("培训计划", [])
            planned = {str(plan.get("计划名称", "")) for plan in plans}
            added = 0
            for course in rule["必训课程"]:
                if course in planned:
                    continue
                plans.append({
                    "计划名称": course,
                    "计划日期": (date.today() + timedelta(days=30)).isoformat(),
                    "计划状态": "待完成",
                })
                added += 1
            if not added:
                return self._refresh(entry), "岗位必训课程均已列入培训计划"
            return self._refresh(entry), f"已按岗位规则新增 {added} 门培训计划"
        if action == "完成培训":
            for plan in entry.get("培训计划", []):
                if plan.get("计划状态") == "待完成":
                    plan["计划状态"] = "已完成"
                    plan["完成日期"] = date.today().isoformat()
                    return self._refresh(entry), f"培训「{plan.get('计划名称', '')}」已标记完成"
            return None, "没有待完成的培训计划"
        return None, f"动作「{action}」不属于员工培训可执行范围"

    def _existing_codes(self) -> set[str]:
        return {str(row.get("员工编号", "")) for row in store.rows(MODULE)}

    def _validate_row(
        self,
        values: dict[str, str],
        *,
        existing: set[str],
        batch_seen: set[str],
    ) -> list[str]:
        """单行校验：重复人员、证书缺失、日期格式等问题都汇总成可读原因。"""
        reasons: list[str] = []
        code = values.get("员工编号", "")
        position = values.get("岗位", "")
        cert_name = values.get("证书名称", "")
        expiry_text = values.get("有效期至", "")

        missing = [label for label in ("员工编号", "姓名", "岗位") if not values.get(label)]
        if missing:
            reasons.append(f"缺少必填字段：{'、'.join(missing)}")

        rule = POSITION_RULES.get(position)
        if position and rule is None:
            reasons.append(f"岗位「{position}」未配置岗位规则")

        if not cert_name:
            reasons.append("证书缺失：未填写证书名称")
        elif rule is not None and cert_name not in rule["必备证书"]:
            reasons.append(f"证书缺失：岗位「{position}」要求持有「{'、'.join(rule['必备证书'])}」")

        if parse_date(expiry_text) is None:
            reasons.append(f"日期格式不合法：有效期至「{expiry_text or '空'}」应为 YYYY-MM-DD")

        if code:
            if code in batch_seen:
                reasons.append(f"重复人员：员工编号 {code} 在本次导入中重复")
            elif code in existing:
                reasons.append(f"重复人员：员工编号 {code} 已存在，未覆盖原有记录")
        return reasons

    def _build_entry(self, values: dict[str, str]) -> dict[str, Any]:
        rows = store.rows(MODULE)
        entry: dict[str, Any] = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
        entry["员工编号"] = values["员工编号"]
        entry["姓名"] = values["姓名"]
        entry["岗位"] = values["岗位"]
        entry["证书列表"] = [{
            "证书名称": values["证书名称"],
            "证书编号": values.get("证书编号", ""),
            "有效期至": values["有效期至"],
        }]
        entry["培训计划"] = []
        rows.append(entry)
        return self._refresh(entry)

    def _refresh_all(self) -> None:
        today = date.today()
        for row in store.rows(MODULE):
            self._refresh(row, today)

    def _refresh(self, row: dict[str, Any], today: date | None = None) -> dict[str, Any]:
        """从证书列表重新推导资格状态：每次读取都重算，重新进入时口径一致。"""
        today = today or date.today()
        position = str(row.get("岗位", ""))
        rule = POSITION_RULES.get(position, {})
        required = list(rule.get("必备证书", []))
        remind_days = int(rule.get("提醒阈值天数", DEFAULT_REMIND_DAYS))
        certs = row.setdefault("证书列表", [])

        for cert in certs:
            expiry = parse_date(cert.get("有效期至"))
            cert["剩余天数"] = (expiry - today).days if expiry is not None else None
            cert["证书状态"] = cert_state(expiry, today, remind_days) if expiry is not None else "证书缺失"

        worst = "持证有效"
        nearest: date | None = None
        for name in required:
            cert = next((item for item in certs if item.get("证书名称") == name), None)
            expiry = parse_date(cert.get("有效期至")) if cert is not None else None
            state = cert_state(expiry, today, remind_days) if expiry is not None else "证书缺失"
            if SEVERITY[state] > SEVERITY[worst]:
                worst = state
            if expiry is not None and (nearest is None or expiry < nearest):
                nearest = expiry

        row["必备证书"] = "、".join(required)
        row["最近到期日"] = nearest.isoformat() if nearest is not None else ""
        row["剩余天数"] = (nearest - today).days if nearest is not None else None
        row["资格状态"] = worst
        row["上岗资格"] = "可上岗" if worst in QUALIFIED_STATUSES else "不可上岗"
        row["status"] = worst
        row["pending"] = worst in ("临期提醒", "今日到期")
        row["abnormal"] = worst in ("已超期", "证书缺失")
        return row
