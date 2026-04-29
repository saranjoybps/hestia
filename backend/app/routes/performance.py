from collections import defaultdict
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.dependencies import get_current_user, require_role, supabase
from app.models import PerformanceReviewCreate, PerformanceReviewUpdate
from app.services.audit_log import log_audit_event
from app.supabase_helper import SupabaseHelper

router = APIRouter(prefix="/performance", tags=["Performance"])


class ApprovalRequest(BaseModel):
    approvedBy: str
    approverName: str


class RejectionRequest(BaseModel):
    rejectedBy: str
    rejectionReason: str


async def _review_to_public(row: Dict[str, Any]) -> Dict[str, Any]:
    user = await SupabaseHelper.get_public_user_by_id(row.get("user_id")) if row.get("user_id") else None
    reviewer = await SupabaseHelper.get_public_user_by_id(row.get("reviewer_id")) if row.get("reviewer_id") else None
    approver = await SupabaseHelper.get_public_user_by_id(row.get("approved_by")) if row.get("approved_by") else None
    rejected_by = await SupabaseHelper.get_public_user_by_id(row.get("rejected_by")) if row.get("rejected_by") else None
    return {
        "id": str(row.get("id")),
        "userId": user.get("uid") if user else None,
        "userName": row.get("user_name") or (user.get("name") if user else None),
        "userEmail": row.get("user_email") or (user.get("email") if user else None),
        "reviewerId": reviewer.get("uid") if reviewer else None,
        "reviewerName": row.get("reviewer_name") or (reviewer.get("name") if reviewer else None),
        "reviewerRole": row.get("reviewer_role"),
        "reviewType": row.get("review_type"),
        "rating": row.get("rating", 0),
        "context": row.get("context"),
        "reviewDate": row.get("review_date"),
        "department": row.get("department"),
        "designation": row.get("designation"),
        "status": row.get("status"),
        "approvedBy": approver.get("uid") if approver else None,
        "approverName": row.get("approver_name") or (approver.get("name") if approver else None),
        "approvalDate": row.get("approval_date"),
        "rejectedBy": rejected_by.get("uid") if rejected_by else None,
        "rejectionReason": row.get("rejection_reason"),
        "rejectionDate": row.get("rejection_date"),
        "createdAt": row.get("created_at"),
        "updatedAt": row.get("updated_at"),
    }


@router.post("/")
async def create_performance_review(
    review_data: PerformanceReviewCreate,
    current_user: dict = Depends(get_current_user),
):
    try:
        if review_data.reviewerId != current_user.get("uid"):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot create review for another reviewer")

        user_role = current_user.get("role")
        if user_role not in ["lead", "manager", "director", "hr"]:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions to create reviews")

        employee_row = await SupabaseHelper.get_user_row_by_firebase_uid(review_data.userId)
        reviewer_row = await SupabaseHelper.get_user_row_by_firebase_uid(review_data.reviewerId)
        if not employee_row or not reviewer_row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employee or reviewer not found")

        status_value = "approved" if user_role == "director" else "pending"
        review_row = {
            "user_id": str(employee_row["id"]),
            "user_name": review_data.userName,
            "user_email": review_data.userEmail,
            "reviewer_id": str(reviewer_row["id"]),
            "reviewer_name": review_data.reviewerName,
            "reviewer_role": review_data.reviewerRole,
            "review_type": review_data.reviewType,
            "rating": review_data.rating,
            "context": review_data.context,
            "review_date": review_data.reviewDate,
            "department": review_data.department,
            "designation": review_data.designation,
            "status": status_value,
            "approved_by": None,
            "approver_name": None,
            "approval_date": None,
            "rejected_by": None,
            "rejection_reason": None,
            "rejection_date": None,
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
        }

        if user_role == "director":
            review_row["approved_by"] = str(reviewer_row["id"])
            review_row["approver_name"] = current_user.get("name", "Unknown")
            review_row["approval_date"] = datetime.utcnow().isoformat()

        response = supabase.table("performance_reviews").insert(review_row).execute()
        inserted = response.data[0] if response.data else None
        if not inserted:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to create performance review")

        review_doc = await _review_to_public(inserted)

        log_audit_event(
            actor_id=current_user.get("uid"),
            actor_name=current_user.get("name"),
            actor_email=current_user.get("email"),
            module="performance",
            action="performance_review_created",
            description=(
                f"{current_user.get('name', 'Someone')} created a performance review for "
                f"{review_doc.get('userName', review_doc.get('userId'))} "
                f"({review_doc.get('reviewType')}, rating {review_doc.get('rating')})."
            ),
            result="success",
            target_type="performance_review",
            target_id=review_doc["id"],
            metadata={
                "user_id": review_doc.get("userId"),
                "user_name": review_doc.get("userName"),
                "review_type": review_doc.get("reviewType"),
                "rating": review_doc.get("rating"),
                "status": review_doc.get("status"),
            },
        )
        return review_doc
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error creating performance review: {str(e)}")


@router.get("/")
async def list_reviews(current_user: dict = Depends(require_role("lead", "manager", "director", "hr"))):
    try:
        current_row = await SupabaseHelper.get_user_row_by_firebase_uid(current_user.get("uid"))
        query = supabase.table("performance_reviews").select("*").order("created_at", desc=True)
        if current_user["role"] == "lead" and current_row:
            query = query.eq("reviewer_id", str(current_row["id"]))
        resp = query.execute()
        return [await _review_to_public(row) for row in (resp.data or [])]
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error fetching performance reviews: {str(e)}")


@router.get("/pending-approvals")
async def get_pending_approvals(current_user: dict = Depends(require_role("director"))):
    try:
        resp = supabase.table("performance_reviews").select("*").eq("status", "pending").order("created_at", desc=True).execute()
        return [await _review_to_public(row) for row in (resp.data or [])]
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error fetching pending reviews: {str(e)}")


@router.post("/{review_id}/approve")
async def approve_review(review_id: str, approval: ApprovalRequest, current_user: dict = Depends(require_role("director"))):
    try:
        if approval.approvedBy != current_user.get("uid"):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot approve as another user")

        doc = supabase.table("performance_reviews").select("*").eq("id", review_id).execute()
        if not doc.data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Review not found")

        review_data = doc.data[0]
        if review_data.get("status") != "pending":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Review is not pending approval")

        approver_row = await SupabaseHelper.get_user_row_by_firebase_uid(current_user.get("uid"))
        update_resp = supabase.table("performance_reviews").update({
            "status": "approved",
            "approved_by": str(approver_row["id"]) if approver_row else None,
            "approver_name": approval.approverName,
            "approval_date": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
        }).eq("id", review_id).execute()
        updated = update_resp.data[0] if update_resp.data else None
        if not updated:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to approve review")

        log_audit_event(
            actor_id=current_user.get("uid"),
            actor_name=current_user.get("name"),
            actor_email=current_user.get("email"),
            module="performance",
            action="performance_review_approved",
            description=(
                f"{current_user.get('name', 'Someone')} approved a performance review for "
                f"{review_data.get('user_name', review_data.get('user_id'))} "
                f"({review_data.get('review_type')}, rating {review_data.get('rating')})."
            ),
            result="success",
            target_type="performance_review",
            target_id=review_id,
            metadata={
                "user_id": review_data.get("user_id"),
                "user_name": review_data.get("user_name"),
                "review_type": review_data.get("review_type"),
                "rating": review_data.get("rating"),
                "status": "approved",
            },
        )
        return {"message": "Review approved successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error approving review: {str(e)}")


@router.post("/{review_id}/reject")
async def reject_review(review_id: str, rejection: RejectionRequest, current_user: dict = Depends(require_role("director"))):
    try:
        if rejection.rejectedBy != current_user.get("uid"):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot reject as another user")

        doc = supabase.table("performance_reviews").select("*").eq("id", review_id).execute()
        if not doc.data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Review not found")

        review_data = doc.data[0]
        if review_data.get("status") != "pending":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Review is not pending approval")

        rejector_row = await SupabaseHelper.get_user_row_by_firebase_uid(current_user.get("uid"))
        update_resp = supabase.table("performance_reviews").update({
            "status": "rejected",
            "rejected_by": str(rejector_row["id"]) if rejector_row else None,
            "rejection_reason": rejection.rejectionReason,
            "rejection_date": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
        }).eq("id", review_id).execute()
        if not update_resp.data:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to reject review")

        log_audit_event(
            actor_id=current_user.get("uid"),
            actor_name=current_user.get("name"),
            actor_email=current_user.get("email"),
            module="performance",
            action="performance_review_rejected",
            description=(
                f"{current_user.get('name', 'Someone')} rejected a performance review for "
                f"{review_data.get('user_name', review_data.get('user_id'))}. "
                f"Reason: {rejection.rejectionReason}."
            ),
            result="success",
            target_type="performance_review",
            target_id=review_id,
            metadata={
                "user_id": review_data.get("user_id"),
                "user_name": review_data.get("user_name"),
                "review_type": review_data.get("review_type"),
                "rating": review_data.get("rating"),
                "status": "rejected",
                "rejection_reason": rejection.rejectionReason,
            },
        )
        return {"message": "Review rejected"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error rejecting review: {str(e)}")


@router.get("/stats")
async def get_performance_stats(current_user: dict = Depends(require_role("hr", "director"))):
    try:
        approved_resp = supabase.table("performance_reviews").select("*").eq("status", "approved").execute()
        pending_resp = supabase.table("performance_reviews").select("*").eq("status", "pending").execute()

        reviews = approved_resp.data or []
        pending_count = len(pending_resp.data or [])
        total_reviews = len(reviews)
        total_rating = sum(float(review.get("rating", 0) or 0) for review in reviews)
        avg_rating = total_rating / total_reviews if total_reviews > 0 else 0

        by_department: Dict[str, Dict[str, Any]] = {}
        user_ratings: Dict[str, Dict[str, Any]] = {}
        rating_distribution = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}

        for review in reviews:
            dept = review.get("department", "Unknown")
            by_department.setdefault(dept, {"count": 0, "total_rating": 0})
            by_department[dept]["count"] += 1
            by_department[dept]["total_rating"] += float(review.get("rating", 0) or 0)

            rating = int(review.get("rating", 0) or 0)
            if 1 <= rating <= 5:
                rating_distribution[rating] = rating_distribution.get(rating, 0) + 1

            user_id = review.get("user_id")
            if user_id not in user_ratings:
                user_ratings[user_id] = {
                    "userId": review.get("user_id"),
                    "userName": review.get("user_name", "Unknown"),
                    "ratings": [],
                }
            user_ratings[user_id]["ratings"].append(float(review.get("rating", 0) or 0))

        dept_stats = {
            dept: {"count": data["count"], "avgRating": round(data["total_rating"] / data["count"], 2)}
            for dept, data in by_department.items()
        }

        top_performers = []
        for _, data in user_ratings.items():
            avg = sum(data["ratings"]) / len(data["ratings"]) if data["ratings"] else 0
            top_performers.append({
                "userId": data["userId"],
                "userName": data["userName"],
                "avgRating": round(avg, 2),
                "reviewCount": len(data["ratings"]),
            })
        top_performers.sort(key=lambda x: (-x["avgRating"], -x["reviewCount"]))
        top_performers = top_performers[:5]

        return {
            "totalReviews": total_reviews,
            "pendingApprovals": pending_count,
            "approvedReviews": total_reviews,
            "averageRating": round(avg_rating, 2),
            "byDepartment": dept_stats,
            "topPerformers": top_performers,
            "ratingDistribution": rating_distribution,
        }
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error generating performance stats: {str(e)}")


@router.get("/{review_id}")
async def get_review(review_id: str, current_user: dict = Depends(require_role("lead", "manager", "director", "hr"))):
    try:
        doc = supabase.table("performance_reviews").select("*").eq("id", review_id).single().execute()
        if not doc.data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Review not found")
        return await _review_to_public(doc.data)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error fetching review: {str(e)}")


@router.delete("/{review_id}")
async def delete_review(review_id: str, current_user: dict = Depends(get_current_user)):
    try:
        doc = supabase.table("performance_reviews").select("*").eq("id", review_id).execute()
        if not doc.data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Review not found")

        review_data = doc.data[0]
        current_row = await SupabaseHelper.get_user_row_by_firebase_uid(current_user.get("uid"))
        is_hr = current_user["role"] in ["hr", "director"]
        is_reviewer = current_row and str(review_data.get("reviewer_id")) == str(current_row["id"])
        if not (is_hr or is_reviewer):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

        log_audit_event(
            actor_id=current_user.get("uid"),
            actor_name=current_user.get("name"),
            actor_email=current_user.get("email"),
            module="performance",
            action="performance_review_deleted",
            description=f"{current_user.get('name', 'Someone')} deleted a performance review for {review_data.get('user_name', review_data.get('user_id'))}.",
            result="success",
            target_type="performance_review",
            target_id=review_id,
            metadata={
                "user_id": review_data.get("user_id"),
                "user_name": review_data.get("user_name"),
                "review_type": review_data.get("review_type"),
                "rating": review_data.get("rating"),
                "status": review_data.get("status"),
            },
        )

        supabase.table("performance_reviews").delete().eq("id", review_id).execute()
        return {"message": "Review deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error deleting review: {str(e)}")
