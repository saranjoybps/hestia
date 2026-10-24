from datetime import date, datetime, timezone
import re
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.dependencies import require_role, supabase
from app.models import (
    AssetCatalogCreate, AssetCatalogUpdate, AssetCategoryCreate, AssetCategoryUpdate, AssetIssueBatch, AssetItemCreate, AssetItemUpdate,
    AssetRequestCreate, AssetRequestReview, AssetReturnComplete, AssetReturnRequest, AssetStockReceive,
)
from app.services.audit_log import log_audit_event
from app.supabase_helper import SupabaseHelper

router = APIRouter(prefix="/assets", tags=["Assets"])
ADMIN_ROLES = {"hr", "director", "super_admin"}
READ_ROLES = ADMIN_ROLES | {"manager", "lead", "employee"}


def _uuid(value: str, label: str) -> str:
    try:
        return str(UUID(str(value)))
    except (ValueError, TypeError):
        raise HTTPException(status_code=422, detail=f"Invalid {label}")


async def _actor(user: Dict[str, Any]) -> Dict[str, Any]:
    row = await SupabaseHelper.get_user_row_by_firebase_uid(str(user.get("uid") or ""))
    if not row:
        raise HTTPException(status_code=404, detail="Current user not found")
    return row


async def _resolve_user(identifier: str) -> Optional[Dict[str, Any]]:
    row = await SupabaseHelper.get_user_row_by_firebase_uid(str(identifier))
    if row:
        return row
    try:
        return await SupabaseHelper.get_user_row_by_id(str(UUID(str(identifier))))
    except ValueError:
        return None


async def _scope_ids(actor: Dict[str, Any], role: str) -> set[str]:
    scope = {str(actor["id"])}
    if role not in {"manager", "lead"}:
        return scope
    reportees = await SupabaseHelper.get_reportees(str(actor.get("firebase_uid") or ""))
    scope.update(str(row.get("id")) for row in reportees if row.get("id"))
    if role == "manager" and actor.get("department"):
        rows = supabase.table("users").select("id").eq("status", "active").eq("department", actor["department"]).execute().data or []
        scope.update(str(row["id"]) for row in rows if row.get("id"))
    return scope


async def _ensure_employee_scope(employee: Dict[str, Any], actor: Dict[str, Any], role: str) -> None:
    if role in ADMIN_ROLES:
        return
    if str(employee.get("id")) in await _scope_ids(actor, role):
        return
    raise HTTPException(status_code=403, detail="This employee is outside your reporting scope")


def _audit(user: Dict[str, Any], action: str, detail: str, target_type: str, target_id: str, metadata: Optional[dict] = None) -> None:
    log_audit_event(actor_id=user.get("uid"), actor_name=user.get("name"), actor_email=user.get("email"), module="assets", action=action, description=detail, result="success", target_type=target_type, target_id=target_id, metadata=metadata or {})


def _catalog_map() -> tuple[dict[str, dict], dict[str, dict]]:
    catalog_rows = supabase.table("asset_catalog").select("*").execute().data or []
    category_rows = supabase.table("asset_categories").select("*").execute().data or []
    categories = {str(row["id"]): row for row in category_rows}
    catalogs = {str(row["id"]): {**row, "category": categories.get(str(row.get("category_id")))} for row in catalog_rows}
    return catalogs, categories


def _exact_count(query: Any) -> int:
    response = query.execute()
    return int(response.count or 0)


@router.get("/options")
async def asset_options(current_user: dict = Depends(require_role(*READ_ROLES))):
    actor = await _actor(current_user)
    role = str(current_user.get("role"))
    catalogs, categories = _catalog_map()
    departments = supabase.table("departments").select("id,name").order("name").execute().data or [] if role in ADMIN_ROLES else ([{"id": None, "name": actor.get("department")}] if actor.get("department") else [])
    if role in ADMIN_ROLES:
        people = supabase.table("users").select("id,firebase_uid,name,last_name,email,role,department,designation").eq("status", "active").order("name").limit(1000).execute().data or []
    else:
        if role == "manager":
            reportees = await SupabaseHelper.get_reportees(str(actor.get("firebase_uid") or ""))
            scope = {str(actor["id"])} | {str(row.get("id")) for row in reportees if row.get("id")}
        else:
            scope = await _scope_ids(actor, role)
        people = supabase.table("users").select("id,firebase_uid,name,last_name,email,role,department,designation").in_("id", list(scope)).eq("status", "active").order("name").limit(1000).execute().data if scope else []
    return {
        "catalog": [{"id": key, "name": row.get("name"), "trackingMode": row.get("tracking_mode"), "categoryId": row.get("category_id"), "categoryName": (row.get("category") or {}).get("name")} for key, row in catalogs.items() if row.get("active")],
        "categories": [{"id": key, "name": row.get("name"), "requiresReturn": row.get("requires_return"), "active": row.get("active")} for key, row in categories.items()],
        "departments": departments,
        "employees": [{"id": row.get("id"), "uid": row.get("firebase_uid"), "name": " ".join(filter(None, [row.get("name"), row.get("last_name")])), "email": row.get("email"), "role": row.get("role"), "department": row.get("department"), "designation": row.get("designation")} for row in (people or [])],
        "currentEmployeeId": str(actor.get("id")),
    }


@router.get("/summary")
async def asset_summary(current_user: dict = Depends(require_role(*READ_ROLES))):
    actor = await _actor(current_user)
    role = str(current_user.get("role"))
    active_statuses = ["issued", "partially_returned", "return_requested", "overdue"]
    overdue_statuses = ["issued", "partially_returned"]
    if role in ADMIN_ROLES:
        balances = supabase.table("asset_stock_balances").select("quantity_available,quantity_total").execute().data or []
        available = _exact_count(supabase.table("asset_items").select("id", count="exact", head=True).in_("status", ["available", "returned"])) + sum(int(row.get("quantity_available") or 0) for row in balances)
        issued_count = _exact_count(supabase.table("asset_assignments").select("id", count="exact", head=True).in_("status", active_statuses))
        returned_count = _exact_count(supabase.table("asset_assignments").select("id", count="exact", head=True).eq("status", "returned"))
        pending_count = _exact_count(supabase.table("asset_requests").select("id", count="exact", head=True).eq("status", "pending"))
        overdue_count = _exact_count(supabase.table("asset_assignments").select("id", count="exact", head=True).lt("due_date", date.today().isoformat()).in_("status", overdue_statuses))
    elif role == "manager":
        scope = list(await _scope_ids(actor, role))
        issued_count = _exact_count(supabase.table("asset_assignments").select("id", count="exact", head=True).in_("employee_id", scope).in_("status", active_statuses))
        returned_count = _exact_count(supabase.table("asset_assignments").select("id", count="exact", head=True).in_("employee_id", scope).eq("status", "returned"))
        overdue_count = _exact_count(supabase.table("asset_assignments").select("id", count="exact", head=True).in_("employee_id", scope).lt("due_date", date.today().isoformat()).in_("status", overdue_statuses))
        team = await SupabaseHelper.get_reportees(str(actor.get("firebase_uid") or ""))
        request_scope = {str(actor["id"])} | {str(row.get("id")) for row in team if row.get("id")}
        pending_count = _exact_count(supabase.table("asset_requests").select("id", count="exact", head=True).in_("employee_id", list(request_scope)).eq("status", "pending"))
        available = _exact_count(supabase.table("asset_items").select("id", count="exact", head=True).eq("department", actor.get("department") or "__none__").in_("status", ["available", "returned"]))
    else:
        scope = list(await _scope_ids(actor, role))
        issued_count = _exact_count(supabase.table("asset_assignments").select("id", count="exact", head=True).in_("employee_id", scope).in_("status", active_statuses)) if scope else 0
        returned_count = _exact_count(supabase.table("asset_assignments").select("id", count="exact", head=True).in_("employee_id", scope).eq("status", "returned")) if scope else 0
        overdue_count = _exact_count(supabase.table("asset_assignments").select("id", count="exact", head=True).in_("employee_id", scope).lt("due_date", date.today().isoformat()).in_("status", overdue_statuses)) if scope else 0
        request_scope = scope
        if role == "lead":
            request_scope = [str(actor["id"])]
        pending_count = _exact_count(supabase.table("asset_requests").select("id", count="exact", head=True).in_("employee_id", request_scope).eq("status", "pending")) if request_scope else 0
        available = 0
    return {
        "available": available,
        "issued": issued_count,
        "returned": returned_count,
        "pendingRequests": pending_count,
        "overdue": overdue_count,
    }


@router.get("/categories")
async def list_asset_categories(current_user: dict = Depends(require_role(*READ_ROLES))):
    rows = supabase.table("asset_categories").select("*").order("name").execute().data or []
    return {"categories": rows}


@router.post("/categories", status_code=status.HTTP_201_CREATED)
async def create_asset_category(payload: AssetCategoryCreate, current_user: dict = Depends(require_role(*ADMIN_ROLES))):
    actor = await _actor(current_user)
    row = {"name": payload.name.strip(), "description": payload.description, "requires_return": payload.requiresReturn, "created_by": actor["id"]}
    try:
        result = supabase.table("asset_categories").insert(row).execute()
    except Exception as exc:
        raise HTTPException(status_code=409, detail=f"Category could not be saved: {exc}")
    created = result.data[0]
    _audit(current_user, "asset_category_created", f"Created asset category {created['name']}.", "asset_category", str(created["id"]))
    return created


@router.patch("/categories/{category_id}")
async def update_asset_category(category_id: str, payload: AssetCategoryUpdate, current_user: dict = Depends(require_role(*ADMIN_ROLES))):
    actor = await _actor(current_user)
    category_id = _uuid(category_id, "category id")
    changes = payload.model_dump(exclude_unset=True)
    if "requiresReturn" in changes:
        changes["requires_return"] = changes.pop("requiresReturn")
    changes["updated_at"] = datetime.now(timezone.utc).isoformat()
    rows = supabase.table("asset_categories").update(changes).eq("id", category_id).execute().data or []
    if not rows:
        raise HTTPException(status_code=404, detail="Asset category not found")
    _audit(current_user, "asset_category_updated", f"Updated asset category {rows[0]['name']}.", "asset_category", category_id)
    return rows[0]


@router.post("/catalog", status_code=status.HTTP_201_CREATED)
async def create_asset_catalog(payload: AssetCatalogCreate, current_user: dict = Depends(require_role(*ADMIN_ROLES))):
    actor = await _actor(current_user)
    category_id = _uuid(payload.categoryId, "category id")
    if not (supabase.table("asset_categories").select("id").eq("id", category_id).eq("active", True).limit(1).execute().data or []):
        raise HTTPException(status_code=404, detail="Active asset category not found")
    row = {"category_id": category_id, "name": payload.name.strip(), "manufacturer": payload.manufacturer, "model": payload.model, "tracking_mode": payload.trackingMode, "notes": payload.notes, "created_by": actor["id"]}
    try:
        result = supabase.table("asset_catalog").insert(row).execute()
    except Exception as exc:
        raise HTTPException(status_code=409, detail=f"Asset type could not be saved: {exc}")
    created = result.data[0]
    if payload.trackingMode == "bulk":
        supabase.table("asset_stock_balances").insert({"catalog_id": created["id"], "quantity_total": 0, "quantity_available": 0}).execute()
    _audit(current_user, "asset_catalog_created", f"Created asset type {created['name']}.", "asset_catalog", str(created["id"]))
    return created


@router.patch("/catalog/{catalog_id}")
async def update_asset_catalog(catalog_id: str, payload: AssetCatalogUpdate, current_user: dict = Depends(require_role(*ADMIN_ROLES))):
    catalog_id = _uuid(catalog_id, "catalog id")
    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(status_code=422, detail="Provide at least one catalog field to update")
    changes["updated_at"] = datetime.now(timezone.utc).isoformat()
    rows = supabase.table("asset_catalog").update(changes).eq("id", catalog_id).execute().data or []
    if not rows:
        raise HTTPException(status_code=404, detail="Asset type not found")
    _audit(current_user, "asset_catalog_updated", f"Updated asset type {rows[0]['name']}.", "asset_catalog", catalog_id)
    return rows[0]


@router.post("/items", status_code=status.HTTP_201_CREATED)
async def create_asset_item(payload: AssetItemCreate, current_user: dict = Depends(require_role(*ADMIN_ROLES))):
    actor = await _actor(current_user)
    catalog_id = _uuid(payload.catalogId, "catalog id")
    catalog_rows = supabase.table("asset_catalog").select("id,tracking_mode,active").eq("id", catalog_id).limit(1).execute().data or []
    if not catalog_rows or not catalog_rows[0].get("active") or catalog_rows[0].get("tracking_mode") != "serialized":
        raise HTTPException(status_code=422, detail="Choose an active serialized asset type")
    row = {"catalog_id": catalog_id, "asset_tag": payload.assetTag.strip(), "serial_number": payload.serialNumber, "department": payload.department, "location": payload.location, "purchase_date": payload.purchaseDate, "purchase_cost": payload.purchaseCost, "warranty_expires_at": payload.warrantyExpiresAt, "condition": payload.condition, "status": "available", "notes": payload.notes, "created_by": actor["id"]}
    try:
        result = supabase.table("asset_items").insert(row).execute()
    except Exception as exc:
        raise HTTPException(status_code=409, detail=f"Asset item could not be saved; asset tag or serial number may already exist: {exc}")
    created = result.data[0]
    _audit(current_user, "asset_item_created", f"Registered asset item {created['asset_tag']}.", "asset_item", str(created["id"]))
    return created


@router.patch("/items/{item_id}")
async def update_asset_item(item_id: str, payload: AssetItemUpdate, current_user: dict = Depends(require_role(*ADMIN_ROLES))):
    item_id = _uuid(item_id, "asset item id")
    changes = payload.model_dump(exclude_unset=True)
    rows = supabase.table("asset_items").select("*").eq("id", item_id).limit(1).execute().data or []
    if not rows:
        raise HTTPException(status_code=404, detail="Asset item not found")
    item = rows[0]
    if "status" in changes:
        active = supabase.table("asset_assignments").select("id").eq("asset_item_id", item_id).in_("status", ["issued", "partially_returned", "return_requested", "overdue"]).limit(1).execute().data or []
        if active:
            raise HTTPException(status_code=409, detail="Return or resolve the active assignment before changing this asset status")
    changes["updated_at"] = datetime.now(timezone.utc).isoformat()
    updated = supabase.table("asset_items").update(changes).eq("id", item_id).execute().data or []
    _audit(current_user, "asset_item_updated", f"Updated asset item {item.get('asset_tag')}.", "asset_item", item_id, {"changed_fields": list(changes)})
    return updated[0] if updated else {**item, **changes}


@router.post("/stock/receive", status_code=status.HTTP_201_CREATED)
async def receive_asset_stock(payload: AssetStockReceive, current_user: dict = Depends(require_role(*ADMIN_ROLES))):
    actor = await _actor(current_user)
    catalog_id = _uuid(payload.catalogId, "catalog id")
    catalog_rows = supabase.table("asset_catalog").select("id,tracking_mode,active,name").eq("id", catalog_id).limit(1).execute().data or []
    if not catalog_rows or not catalog_rows[0].get("active") or catalog_rows[0].get("tracking_mode") != "bulk":
        raise HTTPException(status_code=422, detail="Choose an active bulk asset type")
    result = supabase.rpc("receive_asset_stock", {"p_catalog_id": catalog_id, "p_actor_id": actor["id"], "p_quantity": payload.quantity, "p_reference": payload.reference, "p_notes": payload.notes}).execute()
    _audit(current_user, "asset_stock_received", f"Received {payload.quantity} units of {catalog_rows[0]['name']}.", "asset_catalog", catalog_id, {"quantity": payload.quantity, "reference": payload.reference})
    return result.data


@router.get("")
async def list_assets(
    search: Optional[str] = Query(None, min_length=1, max_length=100),
    category_id: Optional[str] = None,
    status_filter: Optional[str] = Query(None, alias="status"),
    page: int = Query(1, ge=1), limit: int = Query(50, ge=1, le=200),
    current_user: dict = Depends(require_role(*READ_ROLES)),
):
    actor = await _actor(current_user)
    role = str(current_user.get("role"))
    catalogs, categories = _catalog_map()
    query = supabase.table("asset_items").select("*", count="exact")
    if role == "manager":
        query = query.eq("department", actor.get("department") or "__none__")
    elif role not in ADMIN_ROLES:
        query = query.eq("id", "00000000-0000-0000-0000-000000000000")
    if status_filter:
        if status_filter not in {"available", "issued", "returned", "maintenance", "lost", "retired"}:
            raise HTTPException(status_code=422, detail="Unsupported asset status")
        query = query.eq("status", status_filter)
    if search:
        safe_search = re.sub(r"[^A-Za-z0-9 .-]", "", search).strip()
        if safe_search:
            query = query.or_(f"asset_tag.ilike.%{safe_search}%,serial_number.ilike.%{safe_search}%")
    item_response = query.order("created_at", desc=True).range((page-1)*limit, page*limit-1).execute()
    items = item_response.data or []
    if category_id:
        category_id = _uuid(category_id, "category id")
        matching = {key for key, value in catalogs.items() if str(value.get("category_id")) == category_id}
        items = [row for row in items if str(row.get("catalog_id")) in matching]
    balances = supabase.table("asset_stock_balances").select("*").execute().data or [] if role in ADMIN_ROLES else []
    balance_map = {str(row["catalog_id"]): row for row in balances}
    item_catalog_ids = {str(row["catalog_id"]) for row in items}
    items_by_catalog: dict[str, list] = {}
    for item in items:
        items_by_catalog.setdefault(str(item["catalog_id"]), []).append(item)
    catalog_result = []
    for catalog_id, catalog in catalogs.items():
        if not catalog.get("active") or (category_id and str(catalog.get("category_id")) != category_id):
            continue
        if search and search.casefold() not in str(catalog.get("name") or "").casefold() and catalog_id not in item_catalog_ids:
            continue
        visible_items = items_by_catalog.get(catalog_id, []) if role in (ADMIN_ROLES | {"manager"}) else []
        catalog_result.append({"id": catalog_id, "name": catalog.get("name"), "manufacturer": catalog.get("manufacturer"), "model": catalog.get("model"), "trackingMode": catalog.get("tracking_mode"), "categoryId": catalog.get("category_id"), "categoryName": (catalog.get("category") or {}).get("name"), "items": visible_items, "stock": balance_map.get(catalog_id, {"quantity_available": 0, "quantity_total": 0})})
    total = int(item_response.count or 0)
    if category_id or search:
        total = len(catalog_result)
    return {"catalog": catalog_result, "items": items, "total": total, "page": page, "limit": limit, "totalPages": max(1, (total+limit-1)//limit), "categories": list(categories.values())}


@router.get("/assignments")
async def list_asset_assignments(
    employee_id: Optional[str] = None,
    status_filter: Optional[str] = Query(None, alias="status"),
    page: int = Query(1, ge=1), limit: int = Query(50, ge=1, le=200),
    current_user: dict = Depends(require_role(*READ_ROLES)),
):
    actor = await _actor(current_user)
    role = str(current_user.get("role"))
    query = supabase.table("asset_assignments").select("*", count="exact")
    if role not in ADMIN_ROLES:
        scope = await _scope_ids(actor, role)
        if employee_id:
            target = await _resolve_user(employee_id)
            if not target:
                raise HTTPException(status_code=404, detail="Employee not found")
            await _ensure_employee_scope(target, actor, role)
            scope = {str(target["id"])}
        if not scope:
            return {"assignments": [], "total": 0, "page": page, "limit": limit, "totalPages": 1}
        query = query.in_("employee_id", list(scope))
    elif employee_id:
        target = await _resolve_user(employee_id)
        if not target:
            raise HTTPException(status_code=404, detail="Employee not found")
        query = query.eq("employee_id", str(target["id"]))
    if status_filter:
        query = query.eq("status", status_filter)
    response = query.order("issue_date", desc=True).range((page-1)*limit, page*limit-1).execute()
    rows = response.data or []
    catalogs, _ = _catalog_map()
    employee_ids = list({str(row.get("employee_id")) for row in rows if row.get("employee_id")})
    users = {str(row["id"]): row for row in (supabase.table("users").select("id,name,last_name,email").in_("id", employee_ids).execute().data or [])} if employee_ids else {}
    item_ids = list({str(row.get("asset_item_id")) for row in rows if row.get("asset_item_id")})
    items = {str(row["id"]): row for row in (supabase.table("asset_items").select("id,asset_tag,serial_number,condition,status,location").in_("id", item_ids).execute().data or [])} if item_ids else {}
    assignments = []
    for row in rows:
        user = users.get(str(row.get("employee_id")), {})
        asset_item = items.get(str(row.get("asset_item_id")), {})
        effective_status = row.get("status")
        if row.get("due_date") and str(row.get("due_date")) < date.today().isoformat() and effective_status in {"issued", "partially_returned"}:
            effective_status = "overdue"
        catalog = catalogs.get(str(row.get("catalog_id")), {})
        assignments.append({**row, "status": effective_status, "employeeName": " ".join(filter(None, [user.get("name"), user.get("last_name")])), "employeeEmail": user.get("email"), "catalogName": catalog.get("name"), "requiresReturn": bool((catalog.get("category") or {}).get("requires_return", True)), "assetTag": asset_item.get("asset_tag"), "serialNumber": asset_item.get("serial_number"), "condition": asset_item.get("condition"), "location": asset_item.get("location")})
    total = int(response.count or 0)
    return {"assignments": assignments, "total": total, "page": page, "limit": limit, "totalPages": max(1, (total+limit-1)//limit)}


@router.get("/assignments/{assignment_id}")
async def get_asset_assignment(assignment_id: str, current_user: dict = Depends(require_role(*READ_ROLES))):
    actor = await _actor(current_user)
    role = str(current_user.get("role"))
    assignment_id = _uuid(assignment_id, "assignment id")
    rows = supabase.table("asset_assignments").select("*").eq("id", assignment_id).limit(1).execute().data or []
    if not rows:
        raise HTTPException(status_code=404, detail="Asset assignment not found")
    row = rows[0]
    employee = await SupabaseHelper.get_user_row_by_id(str(row["employee_id"]))
    await _ensure_employee_scope(employee, actor, role)
    events = supabase.table("asset_assignment_events").select("*").eq("assignment_id", assignment_id).order("created_at", desc=True).execute().data or []
    actor_ids = list({str(event.get("actor_id")) for event in events if event.get("actor_id")})
    users = {str(row["id"]): row for row in (supabase.table("users").select("id,name,last_name").in_("id", actor_ids).execute().data or [])} if actor_ids else {}
    return {"assignment": row, "events": [{**event, "actorName": users.get(str(event.get("actor_id")), {}).get("name")} for event in events]}


@router.post("/issue-batch", status_code=status.HTTP_201_CREATED)
async def issue_assets(payload: AssetIssueBatch, current_user: dict = Depends(require_role(*ADMIN_ROLES))):
    actor = await _actor(current_user)
    lines = []
    for line in payload.lines:
        employee = await _resolve_user(line.employeeId)
        if not employee or employee.get("status") != "active":
            raise HTTPException(status_code=422, detail="Choose an active employee for every issue")
        catalog_id = _uuid(line.catalogId, "catalog id")
        lines.append({"employee_id": employee["id"], "catalog_id": catalog_id, "asset_item_id": line.assetItemId, "quantity": line.quantity, "request_id": payload.requestId})
    if payload.requestId:
        request_rows = supabase.table("asset_requests").select("id,status,employee_id").eq("id", _uuid(payload.requestId, "request id")).limit(1).execute().data or []
        if not request_rows or request_rows[0].get("status") != "approved":
            raise HTTPException(status_code=409, detail="Only approved asset requests can be fulfilled")
        if any(str(line["employee_id"]) != str(request_rows[0]["employee_id"]) for line in lines):
            raise HTTPException(status_code=422, detail="The issue recipients do not match the approved request")
        requested_items = supabase.table("asset_request_items").select("catalog_id,quantity").eq("request_id", payload.requestId).execute().data or []
        requested = {str(row["catalog_id"]): int(row["quantity"]) for row in requested_items}
        issued = {}
        for line in lines:
            key = str(line["catalog_id"])
            issued[key] = issued.get(key, 0) + int(line["quantity"])
        if issued != requested:
            raise HTTPException(status_code=422, detail="Issue all requested asset types and quantities to fulfil this request")
    try:
        result = supabase.rpc("issue_assets", {"p_actor_id": actor["id"], "p_lines": lines, "p_issue_date": payload.issueDate, "p_due_date": payload.dueDate, "p_notes": payload.notes}).execute()
    except Exception as exc:
        raise HTTPException(status_code=409, detail=f"Issue was not completed: {exc}")
    assignment_ids = [str(value) for value in (result.data or [])]
    _audit(current_user, "assets_issued", f"Issued {len(assignment_ids)} asset assignment(s).", "asset_batch", assignment_ids[0] if assignment_ids else str(actor["id"]), {"assignment_ids": assignment_ids})
    return {"message": "Assets issued", "assignmentIds": assignment_ids}


@router.post("/assignments/{assignment_id}/acknowledge")
async def acknowledge_asset(assignment_id: str, current_user: dict = Depends(require_role(*READ_ROLES))):
    actor = await _actor(current_user)
    assignment_id = _uuid(assignment_id, "assignment id")
    rows = supabase.table("asset_assignments").select("id,employee_id,status").eq("id", assignment_id).limit(1).execute().data or []
    if not rows or str(rows[0].get("employee_id")) != str(actor["id"]):
        raise HTTPException(status_code=404, detail="Assignment not found")
    if rows[0].get("status") not in {"issued", "overdue"}:
        raise HTTPException(status_code=409, detail="This assignment cannot be acknowledged")
    now = datetime.now(timezone.utc).isoformat()
    supabase.table("asset_assignments").update({"acknowledged_at": now, "updated_at": now}).eq("id", assignment_id).execute()
    supabase.table("asset_assignment_events").insert({"assignment_id": assignment_id, "actor_id": actor["id"], "event_type": "acknowledged", "quantity": 0}).execute()
    _audit(current_user, "asset_acknowledged", "Employee acknowledged receipt of an asset.", "asset_assignment", assignment_id)
    return {"message": "Receipt acknowledged"}


@router.post("/assignments/{assignment_id}/return-request")
async def request_asset_return(assignment_id: str, payload: AssetReturnRequest, current_user: dict = Depends(require_role(*READ_ROLES))):
    actor = await _actor(current_user)
    assignment_id = _uuid(assignment_id, "assignment id")
    rows = supabase.table("asset_assignments").select("*").eq("id", assignment_id).limit(1).execute().data or []
    if not rows or str(rows[0].get("employee_id")) != str(actor["id"]):
        raise HTTPException(status_code=404, detail="Assignment not found")
    catalog_rows = supabase.table("asset_catalog").select("category_id").eq("id", rows[0]["catalog_id"]).limit(1).execute().data or []
    category = supabase.table("asset_categories").select("requires_return").eq("id", catalog_rows[0]["category_id"]).limit(1).execute().data if catalog_rows else []
    if category and not category[0].get("requires_return", True):
        raise HTTPException(status_code=409, detail="This asset type does not require return")
    if rows[0].get("status") not in {"issued", "partially_returned", "overdue"}:
        raise HTTPException(status_code=409, detail="This assignment cannot accept a return request")
    now = datetime.now(timezone.utc).isoformat()
    supabase.table("asset_assignments").update({"status": "return_requested", "updated_at": now}).eq("id", assignment_id).execute()
    supabase.table("asset_assignment_events").insert({"assignment_id": assignment_id, "actor_id": actor["id"], "event_type": "return_requested", "quantity": rows[0]["quantity"]-rows[0]["returned_quantity"], "notes": payload.notes}).execute()
    _audit(current_user, "asset_return_requested", "Employee requested to return an asset.", "asset_assignment", assignment_id)
    return {"message": "Return request sent to HR"}


@router.post("/assignments/{assignment_id}/return")
async def complete_asset_return(assignment_id: str, payload: AssetReturnComplete, current_user: dict = Depends(require_role(*ADMIN_ROLES))):
    actor = await _actor(current_user)
    assignment_id = _uuid(assignment_id, "assignment id")
    assignment_rows = supabase.table("asset_assignments").select("catalog_id").eq("id", assignment_id).limit(1).execute().data or []
    if assignment_rows:
        catalog_rows = supabase.table("asset_catalog").select("category_id").eq("id", assignment_rows[0]["catalog_id"]).limit(1).execute().data or []
        category = supabase.table("asset_categories").select("requires_return").eq("id", catalog_rows[0]["category_id"]).limit(1).execute().data if catalog_rows else []
        if category and not category[0].get("requires_return", True):
            raise HTTPException(status_code=409, detail="This asset type does not require return")
    try:
        result = supabase.rpc("complete_asset_return", {"p_assignment_id": assignment_id, "p_actor_id": actor["id"], "p_quantity": payload.quantity, "p_condition": payload.condition, "p_notes": payload.notes}).execute()
    except Exception as exc:
        raise HTTPException(status_code=409, detail=f"Return was not recorded: {exc}")
    _audit(current_user, "asset_return_recorded", "Recorded an asset return.", "asset_assignment", assignment_id, {"quantity": payload.quantity, "condition": payload.condition})
    return result.data


@router.get("/requests")
async def list_asset_requests(current_user: dict = Depends(require_role(*READ_ROLES))):
    actor = await _actor(current_user)
    role = str(current_user.get("role"))
    query = supabase.table("asset_requests").select("*")
    if role not in ADMIN_ROLES:
        if role == "manager":
            reportees = await SupabaseHelper.get_reportees(str(actor.get("firebase_uid") or ""))
            scope = {str(actor["id"])} | {str(row.get("id")) for row in reportees if row.get("id")}
        else:
            scope = await _scope_ids(actor, role)
        query = query.in_("employee_id", list(scope)) if scope else query.eq("employee_id", "00000000-0000-0000-0000-000000000000")
    rows = query.order("created_at", desc=True).limit(300).execute().data or []
    catalogs, _ = _catalog_map()
    employee_ids = list({str(row.get("employee_id")) for row in rows if row.get("employee_id")})
    users = {str(row["id"]): row for row in (supabase.table("users").select("id,name,last_name").in_("id", employee_ids).execute().data or [])} if employee_ids else {}
    request_ids = [str(row["id"]) for row in rows]
    item_rows = supabase.table("asset_request_items").select("*").in_("request_id", request_ids).execute().data or [] if request_ids else []
    items_by_request: dict[str, list] = {}
    for item in item_rows:
        items_by_request.setdefault(str(item["request_id"]), []).append(item)
    result = []
    for row in rows:
        employee = users.get(str(row.get("employee_id")), {})
        items = items_by_request.get(str(row["id"]), [])
        result.append({**row, "employeeName": " ".join(filter(None, [employee.get("name"), employee.get("last_name")])), "items": [{**item, "catalogName": catalogs.get(str(item.get("catalog_id")), {}).get("name")} for item in items]})
    return {"requests": result}


@router.post("/requests", status_code=status.HTTP_201_CREATED)
async def create_asset_request(payload: AssetRequestCreate, current_user: dict = Depends(require_role(*READ_ROLES))):
    actor = await _actor(current_user)
    role = str(current_user.get("role"))
    target = await _resolve_user(payload.employeeId) if payload.employeeId else actor
    if not target or target.get("status") != "active":
        raise HTTPException(status_code=422, detail="Choose an active employee")
    if str(target["id"]) != str(actor["id"]):
        if role == "manager":
            reportees = await SupabaseHelper.get_reportees(str(actor.get("firebase_uid") or ""))
            if str(target["id"]) not in {str(row.get("id")) for row in reportees}:
                raise HTTPException(status_code=403, detail="Managers can submit requests for their reporting team only")
        await _ensure_employee_scope(target, actor, role)
    prepared = []
    for line in payload.lines:
        catalog_id = _uuid(line.catalogId, "catalog id")
        catalog = supabase.table("asset_catalog").select("id,active").eq("id", catalog_id).limit(1).execute().data or []
        if not catalog or not catalog[0].get("active"):
            raise HTTPException(status_code=422, detail="Choose active asset types")
        prepared.append({"catalog_id": catalog_id, "quantity": line.quantity, "notes": line.notes})
    created = supabase.table("asset_requests").insert({"employee_id": target["id"], "department": target.get("department"), "requested_by": actor["id"], "reason": payload.reason, "status": "pending"}).execute().data[0]
    try:
        supabase.table("asset_request_items").insert([{**line, "request_id": created["id"]} for line in prepared]).execute()
    except Exception as exc:
        supabase.table("asset_requests").delete().eq("id", created["id"]).execute()
        raise HTTPException(status_code=500, detail=f"Asset request could not be saved: {exc}")
    _audit(current_user, "asset_requested", "Submitted an asset request.", "asset_request", str(created["id"]))
    return {**created, "items": prepared}


@router.patch("/requests/{request_id}")
async def review_asset_request(request_id: str, payload: AssetRequestReview, current_user: dict = Depends(require_role(*READ_ROLES))):
    actor = await _actor(current_user)
    role = str(current_user.get("role"))
    request_id = _uuid(request_id, "request id")
    rows = supabase.table("asset_requests").select("*").eq("id", request_id).limit(1).execute().data or []
    if not rows:
        raise HTTPException(status_code=404, detail="Asset request not found")
    request_row = rows[0]
    if role not in ADMIN_ROLES:
        if role != "manager":
            if role == "employee" and str(request_row.get("requested_by")) == str(actor["id"]) and payload.status == "rejected":
                raise HTTPException(status_code=403, detail="Use cancellation to withdraw your own request")
            raise HTTPException(status_code=403, detail="Only managers and HR can review asset requests")
        employee = await SupabaseHelper.get_user_row_by_id(str(request_row["employee_id"]))
        reportees = await SupabaseHelper.get_reportees(str(actor.get("firebase_uid") or ""))
        if str(request_row.get("status")) != "pending" or str(employee.get("id")) not in {str(item.get("id")) for item in reportees}:
            raise HTTPException(status_code=403, detail="You can review pending requests from your reporting team only")
    if request_row.get("status") != "pending":
        raise HTTPException(status_code=409, detail="Only pending requests can be reviewed")
    now = datetime.now(timezone.utc).isoformat()
    updated = supabase.table("asset_requests").update({"status": payload.status, "decision_note": payload.decisionNote, "reviewed_by": actor["id"], "reviewed_at": now, "updated_at": now}).eq("id", request_id).execute().data or []
    _audit(current_user, f"asset_request_{payload.status}", f"{payload.status.title()} an asset request.", "asset_request", request_id)
    return updated[0] if updated else {**request_row, "status": payload.status}


@router.delete("/requests/{request_id}")
async def cancel_asset_request(request_id: str, current_user: dict = Depends(require_role(*READ_ROLES))):
    actor = await _actor(current_user)
    request_id = _uuid(request_id, "request id")
    rows = supabase.table("asset_requests").select("id,requested_by,status").eq("id", request_id).limit(1).execute().data or []
    if not rows or str(rows[0].get("requested_by")) != str(actor["id"]):
        raise HTTPException(status_code=404, detail="Request not found")
    if rows[0].get("status") != "pending":
        raise HTTPException(status_code=409, detail="Only pending requests can be cancelled")
    supabase.table("asset_requests").update({"status": "cancelled", "updated_at": datetime.now(timezone.utc).isoformat()}).eq("id", request_id).execute()
    _audit(current_user, "asset_request_cancelled", "Cancelled an asset request.", "asset_request", request_id)
    return {"message": "Asset request cancelled"}


@router.get("/employees/{employee_id}")
async def employee_assets(employee_id: str, current_user: dict = Depends(require_role(*READ_ROLES))):
    actor = await _actor(current_user)
    role = str(current_user.get("role"))
    employee = await _resolve_user(employee_id)
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    await _ensure_employee_scope(employee, actor, role)
    result = await list_asset_assignments(employee_id=str(employee["id"]), page=1, limit=200, current_user=current_user)
    return {"employeeId": employee.get("firebase_uid"), "employeeName": employee.get("name"), **result}

