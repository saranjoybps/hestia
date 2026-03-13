from fastapi import APIRouter, Depends, HTTPException, status
from app.dependencies import db, get_current_user, require_role
from app.models import PerformanceReviewCreate, PerformanceReviewUpdate, PerformanceReviewResponse
from app.services.audit_log import log_audit_event
from datetime import datetime
from typing import Optional, Literal
from pydantic import BaseModel

router = APIRouter(prefix="/performance", tags=["Performance"])

# Additional models for approval/rejection
class ApprovalRequest(BaseModel):
    approvedBy: str
    approverName: str

class RejectionRequest(BaseModel):
    rejectedBy: str
    rejectionReason: str


@router.post("/")
async def create_performance_review(
    review_data: PerformanceReviewCreate,
    current_user: dict = Depends(get_current_user)
):
    """
    Create a performance review
    Leads/Managers/HR can create reviews
    Reviews require director approval unless created by a director
    """
    try:
        # Verify reviewer is current user
        if review_data.reviewerId != current_user.get("uid"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot create review for another reviewer"
            )
        
        user_role = current_user.get("role")
        
        # Check permissions
        if user_role not in ["lead", "manager", "director", "hr"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions to create reviews"
            )
        
        review_doc = review_data.model_dump()
        
        # Determine status based on reviewer role
        # Only directors can auto-approve their own reviews
        if user_role == "director":
            review_doc["status"] = "approved"
            review_doc["approvedBy"] = current_user.get("uid")
            review_doc["approverName"] = current_user.get("name", "Unknown")
            review_doc["approvalDate"] = datetime.utcnow().isoformat()
        else:
            review_doc["status"] = "pending"
        
        review_doc["createdAt"] = datetime.utcnow().isoformat()
        review_doc["updatedAt"] = datetime.utcnow().isoformat()
        
        doc_ref = db.collection("performance_reviews").document()
        doc_ref.set(review_doc)
        
        review_doc["id"] = doc_ref.id

        # Audit log - review created
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
                "status": review_doc.get("status")
            }
        )

        return review_doc
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating performance review: {str(e)}"
        )


@router.get("/")
async def list_reviews(current_user: dict = Depends(require_role("lead", "manager", "director", "hr"))):
    """Get performance reviews based on user role"""
    try:
        reviews_ref = db.collection('performance_reviews')
        
        # Role-based filtering
        if current_user['role'] in ['hr', 'director', 'manager']:
            # HR, Directors, and Managers can see all reviews
            docs = reviews_ref.order_by('createdAt', direction='DESCENDING').stream()
        elif current_user['role'] == 'lead':
            # Leads can see reviews they created
            docs = reviews_ref.where('reviewerId', '==', current_user['uid']).order_by('createdAt', direction='DESCENDING').stream()
        
        reviews = []
        for doc in docs:
            review_data = doc.to_dict()
            review_data['id'] = doc.id
            reviews.append(review_data)
        
        return reviews
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching performance reviews: {str(e)}"
        )


@router.get("/pending-approvals")
async def get_pending_approvals(
    current_user: dict = Depends(require_role("director"))
):
    """Get reviews pending director approval"""
    try:
        # Avoid Firestore composite index by sorting in memory
        docs = db.collection('performance_reviews')\
            .where('status', '==', 'pending')\
            .stream()
        
        reviews = []
        for doc in docs:
            review_data = doc.to_dict()
            review_data['id'] = doc.id
            reviews.append(review_data)
        
        reviews.sort(key=lambda r: r.get('createdAt', ''), reverse=True)
        return reviews
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching pending reviews: {str(e)}"
        )


@router.post("/{review_id}/approve")
async def approve_review(
    review_id: str,
    approval: ApprovalRequest,
    current_user: dict = Depends(require_role("director"))
):
    """Approve a pending performance review (Directors only)"""
    try:
        # Verify approver is current user
        if approval.approvedBy != current_user.get("uid"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot approve as another user"
            )
        
        doc_ref = db.collection('performance_reviews').document(review_id)
        doc = doc_ref.get()
        
        if not doc.exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Review not found"
            )
        
        review_data = doc.to_dict()
        
        if review_data.get('status') != 'pending':
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Review is not pending approval"
            )
        
        # Update review status
        doc_ref.update({
            'status': 'approved',
            'approvedBy': approval.approvedBy,
            'approverName': approval.approverName,
            'approvalDate': datetime.utcnow().isoformat(),
            'updatedAt': datetime.utcnow().isoformat(),
        })

        # Audit log - review approved
        log_audit_event(
            actor_id=current_user.get("uid"),
            actor_name=current_user.get("name"),
            actor_email=current_user.get("email"),
            module="performance",
            action="performance_review_approved",
            description=(
                f"{current_user.get('name', 'Someone')} approved a performance review for "
                f"{review_data.get('userName', review_data.get('userId'))} "
                f"({review_data.get('reviewType')}, rating {review_data.get('rating')})."
            ),
            result="success",
            target_type="performance_review",
            target_id=review_id,
            metadata={
                "user_id": review_data.get("userId"),
                "user_name": review_data.get("userName"),
                "review_type": review_data.get("reviewType"),
                "rating": review_data.get("rating"),
                "status": "approved"
            }
        )
        
        return {"message": "Review approved successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error approving review: {str(e)}"
        )


@router.post("/{review_id}/reject")
async def reject_review(
    review_id: str,
    rejection: RejectionRequest,
    current_user: dict = Depends(require_role("director"))
):
    """Reject a pending performance review (Directors only)"""
    try:
        # Verify rejector is current user
        if rejection.rejectedBy != current_user.get("uid"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot reject as another user"
            )
        
        doc_ref = db.collection('performance_reviews').document(review_id)
        doc = doc_ref.get()
        
        if not doc.exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Review not found"
            )
        
        review_data = doc.to_dict()
        
        if review_data.get('status') != 'pending':
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Review is not pending approval"
            )
        
        # Update review status
        doc_ref.update({
            'status': 'rejected',
            'rejectedBy': rejection.rejectedBy,
            'rejectionReason': rejection.rejectionReason,
            'rejectionDate': datetime.utcnow().isoformat(),
            'updatedAt': datetime.utcnow().isoformat(),
        })

        # Audit log - review rejected
        log_audit_event(
            actor_id=current_user.get("uid"),
            actor_name=current_user.get("name"),
            actor_email=current_user.get("email"),
            module="performance",
            action="performance_review_rejected",
            description=(
                f"{current_user.get('name', 'Someone')} rejected a performance review for "
                f"{review_data.get('userName', review_data.get('userId'))}. "
                f"Reason: {rejection.rejectionReason}."
            ),
            result="success",
            target_type="performance_review",
            target_id=review_id,
            metadata={
                "user_id": review_data.get("userId"),
                "user_name": review_data.get("userName"),
                "review_type": review_data.get("reviewType"),
                "rating": review_data.get("rating"),
                "status": "rejected",
                "rejection_reason": rejection.rejectionReason
            }
        )
        
        return {"message": "Review rejected"}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error rejecting review: {str(e)}"
        )


@router.get("/stats")
async def get_performance_stats(
    current_user: dict = Depends(require_role("hr", "director"))
):
    """Get comprehensive performance statistics"""
    try:
        # Fetch all approved reviews
        docs = db.collection('performance_reviews')\
            .where('status', '==', 'approved')\
            .stream()
        
        reviews = [doc.to_dict() for doc in docs]
        
        # Calculate statistics
        total_reviews = len(reviews)
        
        # Get pending count
        pending_docs = db.collection('performance_reviews')\
            .where('status', '==', 'pending')\
            .stream()
        pending_count = len([doc for doc in pending_docs])
        
        # Calculate average rating
        total_rating = sum(review.get('rating', 0) for review in reviews)
        avg_rating = total_rating / total_reviews if total_reviews > 0 else 0
        
        # By department
        by_department = {}
        for review in reviews:
            dept = review.get('department', 'Unknown')
            if dept not in by_department:
                by_department[dept] = {'count': 0, 'total_rating': 0}
            by_department[dept]['count'] += 1
            by_department[dept]['total_rating'] += review.get('rating', 0)
        
        # Calculate average rating per department
        dept_stats = {}
        for dept, data in by_department.items():
            dept_stats[dept] = {
                'count': data['count'],
                'avgRating': round(data['total_rating'] / data['count'], 2)
            }
        
        # Top performers (by average rating)
        user_ratings = {}
        for review in reviews:
            user_id = review.get('userId')
            if user_id not in user_ratings:
                user_ratings[user_id] = {
                    'userId': user_id,
                    'userName': review.get('userName', 'Unknown'),
                    'ratings': [],
                }
            user_ratings[user_id]['ratings'].append(review.get('rating', 0))
        
        # Calculate average ratings and sort
        top_performers = []
        for user_id, data in user_ratings.items():
            avg = sum(data['ratings']) / len(data['ratings'])
            top_performers.append({
                'userId': user_id,
                'userName': data['userName'],
                'avgRating': round(avg, 2),
                'reviewCount': len(data['ratings'])
            })
        
        # Sort by average rating (descending) and take top 5
        top_performers.sort(key=lambda x: (-x['avgRating'], -x['reviewCount']))
        top_performers = top_performers[:5]
        
        # Rating distribution
        rating_distribution = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
        for review in reviews:
            rating = review.get('rating', 0)
            if 1 <= rating <= 5:
                rating_distribution[rating] = rating_distribution.get(rating, 0) + 1
        
        return {
            'totalReviews': total_reviews,
            'pendingApprovals': pending_count,
            'approvedReviews': total_reviews,
            'averageRating': round(avg_rating, 2),
            'byDepartment': dept_stats,
            'topPerformers': top_performers,
            'ratingDistribution': rating_distribution,
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating performance stats: {str(e)}"
        )


@router.get("/{review_id}")
async def get_review(
    review_id: str,
    current_user: dict = Depends(require_role("lead", "manager", "director", "hr"))
):
    """Get a single performance review"""
    try:
        doc_ref = db.collection('performance_reviews').document(review_id)
        doc = doc_ref.get()
        
        if not doc.exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Review not found"
            )
        
        review_data = doc.to_dict()
        review_data['id'] = doc.id
        
        return review_data
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching review: {str(e)}"
        )


@router.delete("/{review_id}")
async def delete_review(
    review_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Delete a performance review"""
    try:
        doc_ref = db.collection('performance_reviews').document(review_id)
        doc = doc_ref.get()
        
        if not doc.exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Review not found"
            )
        
        review_data = doc.to_dict()
        
        # Only reviewer or HR can delete
        is_hr = current_user['role'] in ['hr', 'director']
        is_reviewer = review_data.get('reviewerId') == current_user['uid']
        
        if not (is_hr or is_reviewer):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )
        
        # Audit log - review deleted
        log_audit_event(
            actor_id=current_user.get("uid"),
            actor_name=current_user.get("name"),
            actor_email=current_user.get("email"),
            module="performance",
            action="performance_review_deleted",
            description=(
                f"{current_user.get('name', 'Someone')} deleted a performance review for "
                f"{review_data.get('userName', review_data.get('userId'))}."
            ),
            result="success",
            target_type="performance_review",
            target_id=review_id,
            metadata={
                "user_id": review_data.get("userId"),
                "user_name": review_data.get("userName"),
                "review_type": review_data.get("reviewType"),
                "rating": review_data.get("rating"),
                "status": review_data.get("status")
            }
        )

        doc_ref.delete()
        return {"message": "Review deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting review: {str(e)}"
        )
