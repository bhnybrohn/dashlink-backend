"""Review service — submit, list, aggregate ratings."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestError, ConflictError
from app.orders.repository import OrderRepository
from app.reviews.models import Review
from app.reviews.repository import ReviewRepository
from app.sellers.repository import SellerProfileRepository


class ReviewService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.review_repo = ReviewRepository(session)
        self.order_repo = OrderRepository(session)
        self.seller_repo = SellerProfileRepository(session)

    async def submit_review(
        self,
        buyer_id: str,
        *,
        order_id: str,
        product_id: str,
        rating: int,
        comment: str | None = None,
    ) -> Review:
        """Submit a review for a delivered order."""
        # Verify the order belongs to the buyer and is delivered
        order = await self.order_repo.get_or_404(order_id)
        if order.buyer_id != buyer_id:
            raise BadRequestError(detail="This order does not belong to you")
        if order.status != "delivered":
            raise BadRequestError(detail="Can only review delivered orders")

        # One review per order
        existing = await self.review_repo.get_by_order(order_id)
        if existing:
            raise ConflictError(detail="You have already reviewed this order")

        review = await self.review_repo.create(
            order_id=order_id,
            buyer_id=buyer_id,
            seller_id=order.seller_id,
            product_id=product_id,
            rating=rating,
            comment=comment,
        )

        # Update seller average rating
        new_avg = await self.review_repo.average_for_seller(order.seller_id)
        await self.seller_repo.update_average_rating(order.seller_id, new_avg)

        return review

    async def list_product_reviews(
        self, product_id: str, *, offset: int = 0, limit: int = 20,
    ) -> tuple[list[Review], int]:
        return await self.review_repo.list_by_product(product_id, offset=offset, limit=limit)

    async def list_seller_reviews(
        self, seller_id: str, *, offset: int = 0, limit: int = 20,
    ) -> tuple[list[Review], int]:
        return await self.review_repo.list_by_seller(seller_id, offset=offset, limit=limit)
