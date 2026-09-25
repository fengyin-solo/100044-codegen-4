"""员工培训与持证上岗接口。

分两组资源：
- /api/training/rules：按岗位维护培训计划（必备证书、培训周期、到期提醒阈值）；
- /api/training/staff：员工持证档案，支持批量导入（逐行返回原因，不覆盖既有记录）。

资格口径由后端每次按当天日期现算，前端重新进入页面读到的证书列表与资格状态天然一致。
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.schemas import ActionResult, EntryPayload, PageResult, TrainingImportPayload
from app.services.training import (
    CALIBERS,
    STAFF_MODULE,
    TrainingService,
)

router = APIRouter(prefix="/api/training", tags=["员工培训与持证上岗"])

service = TrainingService()

STAFF_COLUMNS = ["工号", "姓名", "岗位名称", "所属部门", "证书名称", "发证机构", "发证日期", "到期日期", "资格口径", "持证上岗", "距到期天数", "提醒说明"]
RULE_COLUMNS = ["岗位名称", "岗位类别", "必备证书", "培训周期月", "提前提醒天数", "启用状态"]


@router.get("/rules")
def list_rules(keyword: str | None = Query(default=None, description="按岗位名称检索")) -> dict[str, Any]:
    """读取岗位培训规则；规则数量有限，一次性返回不分页。"""
    items = service.list_rules(keyword=keyword)
    return {"items": items, "total": len(items)}


@router.post("/rules", response_model=ActionResult)
def create_rule(payload: EntryPayload) -> ActionResult:
    """新增岗位培训规则；阈值非法、岗位重复等情况逐条说明原因。"""
    entry, reasons = service.create_rule(payload.values)
    if reasons:
        return ActionResult(ok=False, message="；".join(reasons))
    return ActionResult(ok=True, message=f"岗位培训规则已保存：{entry['岗位名称']}", entry=entry)


@router.patch("/rules/{rule_id}", response_model=ActionResult)
def update_rule(rule_id: int, payload: EntryPayload) -> ActionResult:
    """调整岗位培训规则（含到期提醒阈值）；不允许改成空的必备证书。"""
    entry, reasons = service.update_rule(rule_id, payload.values)
    if entry is None:
        return ActionResult(ok=False, message="；".join(reasons))
    return ActionResult(ok=True, message=f"岗位培训规则已更新：{entry['岗位名称']}", entry=entry)


@router.get("/staff", response_model=PageResult[dict])
def list_staff(
    keyword: str | None = Query(default=None, description="按工号或姓名检索"),
    position: str | None = Query(default=None, description="按岗位名称过滤"),
    caliber: str | None = Query(default=None, description="持证有效、即将到期、今日到期、已超期、证书缺失、岗位未配置"),
    page: int = 1,
    size: int = 20,
) -> PageResult[dict]:
    """员工持证档案列表，资格口径与距到期天数均按当天日期现算。"""
    if size > 200:
        raise HTTPException(status_code=400, detail="每页最多 200 条，请缩小分页范围")
    items, total = service.list_staff(keyword=keyword, position=position, caliber=caliber, page=page, size=size)
    return PageResult(items=items, total=total, page=page, size=size)


@router.post("/staff/import")
def import_staff(payload: TrainingImportPayload) -> dict[str, Any]:
    """一次导入多名员工：每行独立校验，重复人员、证书缺失、日期不合法都给出原因。

    只有全部合法的行才入库；任何已存在工号都被拒绝，提交后绝不覆盖既有记录。
    """
    if not payload.rows:
        raise HTTPException(status_code=400, detail="导入内容为空，请先粘贴员工数据")
    return service.import_staff(payload.rows)


@router.post("/staff", response_model=ActionResult)
def create_staff(payload: EntryPayload) -> ActionResult:
    """登记单名员工持证档案，复用导入的逐字段校验口径。"""
    entry, reasons = service.create_staff(payload.values)
    if reasons:
        return ActionResult(ok=False, message="；".join(reasons))
    return ActionResult(ok=True, message="员工持证档案已登记", entry=entry)


@router.get("/staff/reminders")
def list_reminders(
    scope: str | None = Query(default=None, description="可选：即将到期、今日到期、已超期、证书缺失、岗位未配置"),
) -> dict[str, Any]:
    """证书到期提醒：返回除「持证有效」外需要关注的员工，按到期紧迫程度排序。"""
    items = service.reminders(scope=scope)
    return {"items": items, "total": len(items), "calibers": CALIBERS}


@router.get("/staff/stats")
def staff_stats() -> dict[str, Any]:
    """持证看板：各资格口径人数与可上岗人数，全部现算。"""
    return {"items": service.stats()}


@router.get("/staff/export")
def export_staff(
    keyword: str | None = None,
    position: str | None = None,
    caliber: str | None = None,
) -> dict[str, Any]:
    """导出员工持证档案（含资格口径），口径与列表完全一致。"""
    items, total = service.list_staff(keyword=keyword, position=position, caliber=caliber, page=1, size=10000)
    return {"module": STAFF_MODULE, "total": total, "items": items, "columns": STAFF_COLUMNS}


@router.get("/staff/{staff_id}", response_model=dict)
def get_staff(staff_id: int) -> dict[str, Any]:
    """读取单名员工持证档案与资格判定；不存在时给出可读的错误说明。"""
    entry = service.get_staff(staff_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"员工持证档案 {staff_id} 不存在")
    return entry
