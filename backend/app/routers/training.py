"""员工培训与持证上岗接口：维护员工培训档案、岗位规则、证书到期提醒与批量导入。"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.schemas import ActionResult, EntryPayload, ImportPayload, PageResult
from app.services.training import TrainingService

router = APIRouter(prefix="/api/training", tags=["员工培训"])

service = TrainingService()


@router.get("", response_model=PageResult[dict])
def list_entries(
    keyword: str | None = Query(default=None, description="按员工编号或姓名检索"),
    status: str | None = Query(default=None, description="持证有效、临期提醒、今日到期、已超期、证书缺失"),
    position: str | None = Query(default=None, description="按岗位过滤"),
    page: int = 1,
    size: int = 20,
) -> PageResult[dict]:
    """按员工、岗位与资格状态过滤培训档案；资格状态每次读取都按证书重算。"""
    if size > 200:
        raise HTTPException(status_code=400, detail="每页最多 200 条，请缩小分页范围")
    items, total = service.list_entries(keyword=keyword, status=status, position=position, page=page, size=size)
    return PageResult(items=items, total=total, page=page, size=size)


@router.get("/rules")
def list_rules() -> dict[str, Any]:
    """岗位规则：每个岗位的必备证书、提醒阈值与必训课程。"""
    return {"items": service.list_rules()}


@router.get("/reminders")
def list_reminders() -> dict[str, Any]:
    """证书到期提醒：剩余天数落在岗位提醒阈值内（含到期当天）的必备证书。"""
    items = service.list_reminders()
    return {"items": items, "total": len(items)}


@router.get("/stats")
def qualification_stats() -> dict[str, int]:
    """按资格状态汇总人数，供页头卡片使用。"""
    return service.qualification_stats()


@router.get("/export")
def export_entries() -> dict[str, Any]:
    """导出员工培训档案清单：返回当前全量数据。"""
    items, total = service.list_entries(page=1, size=10000)
    return {"module": "training", "total": total, "items": items}


@router.get("/{entry_id}", response_model=dict)
def get_entry(entry_id: int) -> dict:
    """读取单名员工档案明细；证书列表与资格状态同源推导，重新进入时保持一致。"""
    entry = service.get_entry(entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"员工档案 {entry_id} 不存在或已归档")
    return entry


@router.post("", response_model=ActionResult)
def create_entry(payload: EntryPayload) -> ActionResult:
    """登记单名员工，校验口径与批量导入一致；员工编号已存在时拒绝而不是覆盖。"""
    entry, reasons = service.create_entry(payload.values)
    if reasons:
        return ActionResult(ok=False, message="；".join(reasons))
    return ActionResult(ok=True, message="员工培训档案已登记", entry=entry)


@router.post("/import")
def import_entries(payload: ImportPayload) -> dict[str, Any]:
    """批量导入员工：逐行校验并给出原因，合法行落库，已有记录不会被覆盖。"""
    if not payload.rows:
        return {"ok": False, "message": "没有可导入的内容，请先粘贴员工行", "total": 0, "imported": 0, "failed": 0, "results": []}
    return service.import_entries(payload.rows)


@router.post("/{entry_id}/actions", response_model=ActionResult)
def run_action(entry_id: int, payload: EntryPayload) -> ActionResult:
    """对单名员工执行生成培训计划、完成培训；不允许的动作会被拦下并说明原因。"""
    action = str(payload.values.get("action") or "").strip()
    entry, message = service.run_action(entry_id, action)
    if entry is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message=message, entry=entry)
