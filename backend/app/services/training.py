"""员工培训与持证上岗业务规则。

两张内存表：
- ``position_rule``：按岗位维护的培训计划（必备证书、培训周期、到期前提醒阈值）。
- ``staff``：员工持证档案（工号唯一、证书名称、发证/到期日期）。

资格口径不落库，每次读取都按「岗位规则 + 证书到期日期 + 当天日期」现算，
因此重新进入页面时，证书列表与资格状态必然一致，也避免历史状态残留。

口径划分（到期阈值取自岗位规则的「提前提醒天数」）：
- 持证有效：到期天数 > 阈值；
- 即将到期：0 < 到期天数 <= 阈值（证书到期前按阈值提醒，仍可上岗）；
- 今日到期：到期天数 == 0（到期当天单独一挡，当天仍算持证）；
- 已超期：到期天数 < 0（超期后失去上岗资格，与到期当天口径不同）；
- 证书缺失：没填证书、证书信息不全，或所持证书与岗位必备证书不符；
- 岗位未配置：员工岗位在岗位规则里查不到，无法判定。
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

RULE_MODULE = "position_rule"
STAFF_MODULE = "staff"

# 资格口径常量，路由层与前端都按这套字面值展示/筛选。
QUALIFIED_VALID = "持证有效"
QUALIFYING_SOON = "即将到期"
QUALIFIED_TODAY = "今日到期"
QUALIFIED_EXPIRED = "已超期"
MISSING_CERT = "证书缺失"
RULE_MISSING = "岗位未配置"

CALIBERS = [
    QUALIFIED_VALID,
    QUALIFYING_SOON,
    QUALIFIED_TODAY,
    QUALIFIED_EXPIRED,
    MISSING_CERT,
    RULE_MISSING,
]

RULE_REQUIRED = ["岗位名称", "必备证书"]

# 导入/登记时允许提交的员工字段，顺序即批量导入文本的列顺序。
STAFF_FIELDS = [
    "工号", "姓名", "岗位名称", "所属部门",
    "证书名称", "发证机构", "发证日期", "到期日期", "备注",
]
STAFF_REQUIRED = ["工号", "姓名", "岗位名称"]

MIN_THRESHOLD, MAX_THRESHOLD = 1, 365
MIN_CYCLE_MONTHS, MAX_CYCLE_MONTHS = 1, 60


def parse_canonical_date(value: Any) -> date | None:
    """严格按 YYYY-MM-DD 解析日期。

    空值返回 None（由调用方区分是「没填」还是「格式错」）；
    ``2026/9/1``、``2026-1-1``、``2026-02-31`` 这类一律抛 ValueError，
    交给校验逻辑转成「日期格式不合法」的行级原因。
    """
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    parsed = datetime.strptime(text, "%Y-%m-%d").date()
    if parsed.strftime("%Y-%m-%d") != text:
        raise ValueError("日期必须采用零填充的 YYYY-MM-DD 格式")
    return parsed


def _store():
    """延迟导入内存仓库，避免与 store 初始化阶段互相导入。"""
    from app.store import store

    return store


def _rules_by_position() -> dict[str, dict[str, Any]]:
    return {str(row["岗位名称"]).strip(): row for row in _store().rows(RULE_MODULE)}


def _find_rule(position: str) -> dict[str, Any] | None:
    return _rules_by_position().get(str(position or "").strip())


def _as_int(value: Any) -> int | None:
    """把前端传来的数字/数字字符串转成 int；非法时返回 None。"""
    if value is None or str(value).strip() == "":
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    text = str(value).strip()
    if not text.lstrip("-").isdigit():
        return None
    return int(text)


class TrainingService:
    # ------------------------------------------------------------------ 岗位规则
    def list_rules(self, *, keyword: str | None = None) -> list[dict[str, Any]]:
        rows = _store().rows(RULE_MODULE)
        if keyword:
            rows = [row for row in rows if keyword in str(row.get("岗位名称", ""))]
        return rows

    def create_rule(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        reasons: list[str] = []
        cleaned = {key: str(values.get(key) or "").strip() for key in ["岗位名称", "岗位类别", "必备证书", "备注"]}
        for field in RULE_REQUIRED:
            if not cleaned[field]:
                reasons.append(f"{field}为空")
        threshold, threshold_reasons = self._validate_threshold(values.get("提前提醒天数"), default=30)
        cycle, cycle_reasons = self._validate_cycle(values.get("培训周期月"), default=12)
        reasons.extend(threshold_reasons + cycle_reasons)

        if cleaned["岗位名称"] and _find_rule(cleaned["岗位名称"]):
            reasons.append(f"岗位「{cleaned['岗位名称']}」的培训规则已存在")
        if reasons:
            return None, reasons

        rows = _store().rows(RULE_MODULE)
        entry = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
        entry.update(cleaned)
        entry["培训周期月"] = cycle
        entry["提前提醒天数"] = threshold
        entry["启用状态"] = "启用"
        entry["status"] = "启用"
        entry["pending"] = False
        entry["abnormal"] = False
        rows.append(entry)
        return entry, []

    def update_rule(self, rule_id: int, values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        entry = _store().find(RULE_MODULE, rule_id)
        if entry is None:
            return None, [f"岗位规则 {rule_id} 不存在"]
        reasons: list[str] = []
        for field in ["岗位类别", "必备证书", "备注"]:
            if field in values:
                text = str(values.get(field) or "").strip()
                if field == "必备证书" and not text:
                    reasons.append("必备证书不能为空")
                else:
                    entry[field] = text
        if "提前提醒天数" in values:
            threshold, threshold_reasons = self._validate_threshold(values["提前提醒天数"], default=None)
            reasons.extend(threshold_reasons)
            if threshold is not None:
                entry["提前提醒天数"] = threshold
        if "培训周期月" in values:
            cycle, cycle_reasons = self._validate_cycle(values["培训周期月"], default=None)
            reasons.extend(cycle_reasons)
            if cycle is not None:
                entry["培训周期月"] = cycle
        if "启用状态" in values:
            state = str(values["启用状态"] or "").strip()
            if state not in ("启用", "停用"):
                reasons.append("启用状态只允许填「启用」或「停用」")
            else:
                entry["启用状态"] = state
                entry["status"] = state
        if reasons:
            return None, reasons
        return entry, []

    @staticmethod
    def _validate_threshold(value: Any, *, default: int | None) -> tuple[int | None, list[str]]:
        if value is None or str(value).strip() == "":
            return default, []
        parsed = _as_int(value)
        if parsed is None or not (MIN_THRESHOLD <= parsed <= MAX_THRESHOLD):
            return None, [f"提前提醒天数需为 {MIN_THRESHOLD}-{MAX_THRESHOLD} 之间的整数"]
        return parsed, []

    @staticmethod
    def _validate_cycle(value: Any, *, default: int | None) -> tuple[int | None, list[str]]:
        if value is None or str(value).strip() == "":
            return default, []
        parsed = _as_int(value)
        if parsed is None or not (MIN_CYCLE_MONTHS <= parsed <= MAX_CYCLE_MONTHS):
            return None, [f"培训周期月需为 {MIN_CYCLE_MONTHS}-{MAX_CYCLE_MONTHS} 之间的整数"]
        return parsed, []

    # --------------------------------------------------------------- 持证档案
    def list_staff(
        self,
        *,
        keyword: str | None = None,
        position: str | None = None,
        caliber: str | None = None,
        page: int = 1,
        size: int = 20,
        today: date | None = None,
    ) -> tuple[list[dict[str, Any]], int]:
        today = today or date.today()
        rows = [self.enrich(row, today=today) for row in _store().rows(STAFF_MODULE)]
        if keyword:
            rows = [
                row for row in rows
                if keyword in str(row.get("工号", "")) or keyword in str(row.get("姓名", ""))
            ]
        if position:
            rows = [row for row in rows if str(row.get("岗位名称", "")).strip() == position.strip()]
        if caliber:
            rows = [row for row in rows if row.get("资格口径") == caliber]
        total = len(rows)
        start = max(page - 1, 0) * size
        return rows[start:start + size], total

    def get_staff(self, staff_id: int, *, today: date | None = None) -> dict[str, Any] | None:
        row = _store().find(STAFF_MODULE, staff_id)
        return self.enrich(row, today=today) if row else None

    def create_staff(self, values: dict[str, Any], *, today: date | None = None) -> tuple[dict[str, Any] | None, list[str]]:
        cleaned = self._normalize(values)
        reasons = self._validate_row(cleaned, existing_codes=self._existing_codes(), batch_codes=set())
        if reasons:
            return None, reasons
        return self._insert(cleaned, today=today), []

    def import_staff(
        self,
        rows: list[dict[str, Any]],
        *,
        today: date | None = None,
    ) -> dict[str, Any]:
        """批量导入：逐行校验，合法行入库，非法行只给原因不影响其他行。

        已存在的工号一律拒绝，绝不会覆盖既有记录；同一批次里重复的工号，
        第一条之后都按重复处理。
        """
        today = today or date.today()
        existing_codes = self._existing_codes()
        batch_codes: set[str] = set()
        results: list[dict[str, Any]] = []
        success = 0
        for line, raw in enumerate(rows, start=1):
            cleaned = self._normalize(raw)
            reasons = self._validate_row(cleaned, existing_codes=existing_codes, batch_codes=batch_codes)
            code = cleaned["工号"]
            if reasons:
                results.append({
                    "line": line,
                    "ok": False,
                    "工号": code,
                    "姓名": cleaned["姓名"],
                    "reasons": reasons,
                    "staff": None,
                })
                continue
            entry = self._insert(cleaned, today=today)
            existing_codes.add(code)
            batch_codes.add(code)
            success += 1
            results.append({
                "line": line,
                "ok": True,
                "工号": code,
                "姓名": cleaned["姓名"],
                "reasons": [],
                "staff": entry,
            })

        failed = len(results) - success
        if failed == 0:
            message = f"导入完成：{success} 条全部成功，未改动任何既有记录"
        elif success == 0:
            message = f"导入完成：{failed} 条均未通过校验，没有新增记录，既有记录保持不变"
        else:
            message = f"导入完成：成功 {success} 条、{failed} 条被拒，被拒行未入库，既有记录保持不变"
        return {
            "ok": failed == 0,
            "message": message,
            "total": len(results),
            "success_count": success,
            "failed_count": failed,
            "results": results,
        }

    def reminders(self, *, scope: str | None = None, today: date | None = None) -> list[dict[str, Any]]:
        """到期提醒：默认返回所有需要关注的员工；可按口径单独筛。"""
        today = today or date.today()
        rows = [self.enrich(row, today=today) for row in _store().rows(STAFF_MODULE)]
        rows = [row for row in rows if row["资格口径"] != QUALIFIED_VALID]
        if scope and scope in CALIBERS:
            rows = [row for row in rows if row["资格口径"] == scope]
        rows.sort(key=lambda row: (row.get("距到期天数") is None, row.get("距到期天数", 0)))
        return rows

    def stats(self, *, today: date | None = None) -> dict[str, int]:
        today = today or date.today()
        counts = {caliber: 0 for caliber in CALIBERS}
        for row in _store().rows(STAFF_MODULE):
            counts[self.enrich(row, today=today)["资格口径"]] += 1
        counts["员工总数"] = len(_store().rows(STAFF_MODULE))
        counts["可上岗人数"] = sum(1 for row in _store().rows(STAFF_MODULE) if self.enrich(row, today=today)["持证上岗"])
        return counts

    # --------------------------------------------------------------- 核心判定
    def enrich(self, row: dict[str, Any], *, today: date | None = None) -> dict[str, Any]:
        """在档案行上叠加现算的资格信息，原始档案内容原样保留。"""
        today = today or date.today()
        result = dict(row)
        position = str(row.get("岗位名称") or "").strip()
        rule = _find_rule(position)
        result["必备证书"] = str(rule["必备证书"]) if rule else None
        result["提前提醒天数"] = int(rule["提前提醒天数"]) if rule else None

        cert_name = str(row.get("证书名称") or "").strip()
        expiry_text = str(row.get("到期日期") or "").strip()

        caliber, qualified, days, reason = self._caliber(rule, cert_name, expiry_text, today)
        result["距到期天数"] = days
        result["资格口径"] = caliber
        result["持证上岗"] = qualified
        result["需提醒"] = caliber in (QUALIFYING_SOON, QUALIFIED_TODAY)
        result["提醒说明"] = reason
        return result

    @staticmethod
    def _caliber(
        rule: dict[str, Any] | None,
        cert_name: str,
        expiry_text: str,
        today: date,
    ) -> tuple[str, bool, int | None, str]:
        if rule is None:
            return RULE_MISSING, False, None, "该岗位未配置培训规则，无法判定持证资格"
        required = str(rule.get("必备证书") or "").strip()
        threshold = int(rule.get("提前提醒天数", 30))

        if not cert_name and not expiry_text:
            return MISSING_CERT, False, None, "证书缺失：未登记证书与到期日期"
        if not cert_name:
            return MISSING_CERT, False, None, "证书缺失：只填了到期日期，未登记证书名称"
        if not expiry_text:
            return MISSING_CERT, False, None, "证书缺失：缺少到期日期"
        if required and cert_name != required:
            return MISSING_CERT, False, None, f"所持证书「{cert_name}」与岗位必备证书「{required}」不符"
        try:
            expiry = parse_canonical_date(expiry_text)
        except ValueError:
            return MISSING_CERT, False, None, f"到期日期格式不合法：{expiry_text}"
        assert expiry is not None
        days = (expiry - today).days
        if days < 0:
            return QUALIFIED_EXPIRED, False, days, f"证书已于 {-days} 天前超期，暂停上岗资格"
        if days == 0:
            # 到期当天单独一挡：当天仍视为持证，次日起才算超期。
            return QUALIFIED_TODAY, True, 0, "证书今日到期，今天仍可上岗，请立即复审"
        if days <= threshold:
            return QUALIFYING_SOON, True, days, f"证书将于 {days} 天后到期（阈值 {threshold} 天）"
        return QUALIFIED_VALID, True, days, "证书在有效期内"

    # --------------------------------------------------------------- 校验入库
    @staticmethod
    def _normalize(raw: dict[str, Any]) -> dict[str, str]:
        cleaned = {field: str(raw.get(field) or "").strip() for field in STAFF_FIELDS}
        return cleaned

    @staticmethod
    def _existing_codes() -> set[str]:
        return {str(row.get("工号") or "").strip() for row in _store().rows(STAFF_MODULE)}

    def _validate_row(
        self,
        cleaned: dict[str, str],
        *,
        existing_codes: set[str],
        batch_codes: set[str],
    ) -> list[str]:
        reasons: list[str] = []
        for field in STAFF_REQUIRED:
            if not cleaned[field]:
                reasons.append(f"{field}为空")

        code = cleaned["工号"]
        if code:
            if code in existing_codes:
                reasons.append(f"工号「{code}」已存在，提交不会覆盖既有记录")
            elif code in batch_codes:
                reasons.append(f"工号「{code}」在本次导入中重复")

        position = cleaned["岗位名称"]
        rule = _find_rule(position) if position else None
        if position and rule is None:
            reasons.append(f"岗位「{position}」未配置培训规则")

        cert_name = cleaned["证书名称"]
        issue_text = cleaned["发证日期"]
        expiry_text = cleaned["到期日期"]
        if not cert_name and not expiry_text:
            reasons.append("证书缺失：证书名称与到期日期都未填写")
        elif not cert_name:
            reasons.append("证书缺失：未填写证书名称")
        elif not expiry_text:
            reasons.append("证书缺失：未填写证书到期日期")

        issue = expiry = None
        if issue_text:
            try:
                issue = parse_canonical_date(issue_text)
            except ValueError:
                reasons.append(f"发证日期格式不合法：「{issue_text}」，应为 YYYY-MM-DD")
        if expiry_text:
            try:
                expiry = parse_canonical_date(expiry_text)
            except ValueError:
                reasons.append(f"到期日期格式不合法：「{expiry_text}」，应为 YYYY-MM-DD")
        if issue and expiry and issue > expiry:
            reasons.append("发证日期不能晚于到期日期")
        if rule and cert_name and str(rule.get("必备证书") or "").strip() and cert_name != str(rule["必备证书"]):
            reasons.append(f"所持证书「{cert_name}」与岗位必备证书「{rule['必备证书']}」不符")
        return reasons

    def _insert(self, cleaned: dict[str, str], *, today: date) -> dict[str, Any]:
        rows = _store().rows(STAFF_MODULE)
        entry: dict[str, Any] = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
        entry.update(cleaned)
        enriched = self.enrich(entry, today=today)
        caliber = enriched["资格口径"]
        entry["status"] = caliber
        entry["pending"] = caliber != QUALIFIED_VALID
        entry["abnormal"] = not enriched["持证上岗"]
        rows.append(entry)
        return enriched
