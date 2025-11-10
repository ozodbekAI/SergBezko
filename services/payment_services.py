from yookassa import Configuration, Payment
from config import settings
import uuid
from typing import Tuple
import logging
from database.repositories import UserRepository, PaymentRepository
from sqlalchemy.ext.asyncio import AsyncSession
import asyncio

logger = logging.getLogger(__name__)

Configuration.account_id = settings.YOOKASSA_SHOP_ID
Configuration.secret_key = settings.YOOKASSA_SECRET_KEY



class PaymentService:
    @staticmethod
    async def create_payment(
        session: AsyncSession,
        telegram_id: int,
        credits: int,
        amount: float
    ) -> Tuple[str, str]:
        logger.info(f"create_payment called with: telegram_id={telegram_id}, credits={credits}, amount={amount}")
        
        try:
            user_repo = UserRepository(session)
            user = await user_repo.get_user_by_telegram_id(telegram_id)
            
            if not user:
                raise ValueError(f"User with telegram_id {telegram_id} not found")
            
            logger.info(f"Found user: id={user.id}, telegram_id={user.telegram_id}")
            
            idempotence_key = str(uuid.uuid4())
            
            for attempt in range(3):
                try:
                    logger.info(f"Creating YooKassa payment (attempt {attempt + 1})")
                    payment = Payment.create({
                        "amount": {
                            "value": f"{amount:.2f}",
                            "currency": "RUB"
                        },
                        "confirmation": {
                            "type": "redirect",
                            "return_url": getattr(settings, 'SUCCESS_REDIRECT_URL', None) or f"https://t.me/{getattr(settings, 'BOT_USERNAME', 'bot')}?start=success_{telegram_id}"
                        },
                        "capture": True,
                        "description": f"Пополнение баланса: {credits} кредитов для пользователя {telegram_id}",
                        "receipt": {
                            "customer": {
                                "email": f"user{telegram_id}@telegram.user"  # Yoki haqiqiy email
                            },
                            "items": [
                                {
                                    "description": f"Пополнение баланса: {credits} кредитов",
                                    "quantity": "1",
                                    "amount": {
                                        "value": f"{amount:.2f}",
                                        "currency": "RUB"
                                    },
                                    "vat_code": 1,  # НДС не облагается
                                    "payment_mode": "full_payment",
                                    "payment_subject": "service"
                                }
                            ]
                        },
                        "metadata": {
                            "telegram_id": str(telegram_id),
                            "user_id": str(user.id),
                            "credits": str(credits),
                            "amount": str(amount)
                        }
                    }, idempotence_key)
                    
                    logger.info(f"YooKassa payment created: {payment.id}")

                    payment_repo = PaymentRepository(session)
                    logger.info(f"Calling payment_repo.create_payment with: user_id={user.id}, payment_id={payment.id}, amount={amount}, credits={credits}")
                    
                    db_payment = await payment_repo.create_payment(
                        user_id=user.id,
                        payment_id=payment.id,
                        amount=amount,
                        credits=credits
                    )
                    
                    logger.info(f"DB payment created: {db_payment.id}")
                    logger.info(f"Payment created successfully: {payment.id} for user {telegram_id}, amount {amount} RUB")
                    
                    return payment.confirmation.confirmation_url, payment.id
                    
                except Exception as e:
                    logger.error(f"YooKassa create_payment error (attempt {attempt + 1}): {e}", exc_info=True)
                    
                    if hasattr(e, 'response') and e.response is not None:
                        try:
                            error_details = e.response.json()
                            logger.error(f"YooKassa error details: {error_details}")
                        except:
                            logger.error(f"YooKassa response text: {e.response.text}")
                    
                    if attempt == 2:
                        error_msg = str(e)
                        if hasattr(e, 'response') and e.response is not None:
                            try:
                                error_details = e.response.json()
                                error_msg = f"{error_msg} - Details: {error_details}"
                            except:
                                error_msg = f"{error_msg} - Response: {e.response.text}"
                        raise Exception(f"Failed to create payment: {error_msg}")
                    await asyncio.sleep(1)
                    
        except Exception as e:
            logger.error(f"create_payment failed: {e}", exc_info=True)
            raise
    
    @staticmethod
    async def check_payment_status(payment_id: str, session: AsyncSession) -> dict:
        for attempt in range(3):
            try:
                payment = Payment.find_one(payment_id)
                status_data = {
                    "payment_id": payment.id,
                    "status": payment.status,
                    "paid": payment.paid,
                    "amount": float(payment.amount.value) if payment.amount else 0,
                    "metadata": dict(payment.metadata) if payment.metadata else {}
                }
                
                if payment.paid:
                    payment_repo = PaymentRepository(session)
                    await payment_repo.update_payment_status(payment_id, "succeeded")
                    logger.info(f"Payment {payment_id} marked as succeeded")
                
                return status_data
                
            except Exception as e:
                logger.error(f"YooKassa check_status error (attempt {attempt + 1}): {e}", exc_info=True)
                if attempt == 2:
                    raise
                await asyncio.sleep(1)
    
    @staticmethod
    async def cancel_payment(payment_id: str, session: AsyncSession) -> bool:
        for attempt in range(3):
            try:
                payment = Payment.find_one(payment_id)
                if payment.status == "pending":
                    Payment.cancel(payment_id, str(uuid.uuid4()))
                    payment_repo = PaymentRepository(session)
                    await payment_repo.update_payment_status(payment_id, "cancelled")
                    logger.info(f"Payment {payment_id} cancelled")
                    return True
                return False
            except Exception as e:
                logger.error(f"YooKassa cancel_payment error (attempt {attempt + 1}): {e}", exc_info=True)
                if attempt == 2:
                    return False
                await asyncio.sleep(1)


payment_service = PaymentService()