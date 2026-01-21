import logging
import pprint

from werkzeug import urls

from odoo import _, fields, models
from odoo.exceptions import UserError
from odoo.tools import float_round

_logger = logging.getLogger(__name__)

# CAWL SDK imports with graceful error handling
try:
    from onlinepayments.sdk.domain.address import Address
    from onlinepayments.sdk.domain.amount_of_money import AmountOfMoney
    from onlinepayments.sdk.domain.card_payment_method_specific_input_for_hosted_checkout import (
        CardPaymentMethodSpecificInputForHostedCheckout,
    )
    from onlinepayments.sdk.domain.contact_details import ContactDetails
    from onlinepayments.sdk.domain.create_hosted_checkout_request import (
        CreateHostedCheckoutRequest,
    )
    from onlinepayments.sdk.domain.customer import Customer
    from onlinepayments.sdk.domain.hosted_checkout_specific_input import (
        HostedCheckoutSpecificInput,
    )
    from onlinepayments.sdk.domain.order import Order
    from onlinepayments.sdk.domain.order_references import OrderReferences
    from onlinepayments.sdk.domain.payment_product_filter import PaymentProductFilter
    from onlinepayments.sdk.domain.payment_product_filters_hosted_checkout import (
        PaymentProductFiltersHostedCheckout,
    )
    from onlinepayments.sdk.domain.payment_references import PaymentReferences
    from onlinepayments.sdk.domain.personal_name import PersonalName
    from onlinepayments.sdk.domain.refund_request import RefundRequest

    CAWL_SDK_AVAILABLE = True
    _logger.info("CAWL SDK imported successfully in payment_transaction module")
except ImportError as e:
    CAWL_SDK_AVAILABLE = False
    _logger.error("CAWL SDK import failed in payment_transaction module: %s", str(e))
    _logger.error("Import error details: %s", e)


class PaymentTransaction(models.Model):
    _inherit = "payment.transaction"

    # CAWL specific fields
    cawl_checkout_id = fields.Char(
        string="CAWL Checkout ID",
        help="The checkout ID returned by CAWL hosted checkout API",
    )
    cawl_payment_id = fields.Char(
        string="CAWL Payment ID", help="The payment ID returned by CAWL"
    )

    def _get_specific_rendering_values(self, processing_values):
        """Override to return CAWL-specific rendering values for hosted checkout redirect.

        Note: self.ensure_one() from `_get_processing_values`

        :param dict processing_values: The generic and specific processing values of the transaction
        :return: The dict of provider-specific processing values
        :rtype: dict
        """

        res = super()._get_specific_rendering_values(processing_values)
        if self.provider_code != "cawl":
            return res

        # Create CAWL hosted checkout session
        try:
            checkout_response = self._cawl_create_checkout_session()

            # Store the checkout ID for later reference
            self.cawl_checkout_id = checkout_response.hosted_checkout_id

            rendering_values = {
                "api_url": checkout_response.redirect_url,
                "cawl_checkout_id": checkout_response.hosted_checkout_id,
                "cawl_pspid": self.provider_id.cawl_pspid,
                "amount": self.amount,
                "currency": self.currency_id,
                "reference": self.reference,
                "return_url": processing_values.get("return_url"),
            }

            res.update(rendering_values)

            _logger.info(
                "CAWL checkout session created successfully for transaction %s: %s",
                self.reference,
                checkout_response.hosted_checkout_id,
            )

        except Exception as e:
            _logger.error(
                "CAWL checkout session creation failed for transaction %s: %s",
                self.reference,
                str(e),
            )

            # Provide more specific error messages based on the exception
            error_message = self._get_user_friendly_error_message(str(e))
            raise UserError(error_message)

        return res

    def _cawl_create_checkout_session(self):
        """Create a CAWL hosted checkout session using the SDK."""
        self.ensure_one()

        if not CAWL_SDK_AVAILABLE:
            _logger.error("CAWL SDK not available when creating checkout session")
            raise UserError(_("CAWL SDK not available. Please install dependencies."))

        provider = self.provider_id

        # Initialize CAWL client
        client = self._get_cawl_client()

        # Prepare checkout request
        checkout_request = self._cawl_prepare_checkout_request()

        try:
            # Create hosted checkout session
            response = (
                client.merchant(provider.cawl_pspid)
                .hosted_checkout()
                .create_hosted_checkout(checkout_request)
            )

            _logger.info(
                "CAWL checkout session created successfully: %s",
                response.hosted_checkout_id,
            )
            return response

        except Exception as e:
            _logger.error(
                "CAWL API error during checkout creation for transaction %s: %s",
                self.reference,
                str(e),
            )

            # Map CAWL API errors to user-friendly messages
            if "authentication" in str(e).lower() or "unauthorized" in str(e).lower():
                raise UserError(
                    _("Payment service configuration error. Please contact support.")
                )
            elif "network" in str(e).lower() or "connection" in str(e).lower():
                raise UserError(
                    _(
                        "Unable to connect to payment service. Please check your internet connection and try again."
                    )
                )
            elif "invalid" in str(e).lower() and "currency" in str(e).lower():
                raise UserError(_("This currency is not supported for CAWL payments."))
            elif "amount" in str(e).lower():
                raise UserError(
                    _(
                        "Invalid payment amount. Please check the order total and try again."
                    )
                )
            else:
                raise UserError(_("Payment gateway error: %s") % str(e))

    def _get_cawl_client(self):
        """Get configured CAWL SDK client."""
        provider = self.provider_id

        # Use centralized client method from provider
        return provider._get_cawl_client()

    def _cawl_prepare_checkout_request(self):
        """Prepare the CAWL hosted checkout request."""
        self.ensure_one()

        # Convert amount to cents (CAWL expects integer amounts)
        amount_cents = int(float_round(self.amount * 100, precision_digits=0))

        # Prepare order references
        order_references = OrderReferences()
        order_references.merchant_reference = self.reference

        # Prepare amount of money
        amount_of_money = AmountOfMoney()
        amount_of_money.amount = amount_cents
        amount_of_money.currency_code = self.currency_id.name

        # Prepare customer information
        customer = self._cawl_prepare_customer_data()

        # Prepare order
        order = Order()
        order.amount_of_money = amount_of_money
        order.customer = customer
        order.references = order_references

        # Prepare hosted checkout specific input
        hosted_checkout_input = HostedCheckoutSpecificInput()
        hosted_checkout_input.return_url = self._get_cawl_return_url()
        hosted_checkout_input.show_result_page = (
            False  # Redirect directly back to merchant
        )

        cardPaymentMethodSpecificInputForHostedCheckout = (
            CardPaymentMethodSpecificInputForHostedCheckout()
        )
        cardPaymentMethodSpecificInputForHostedCheckout.group_cards = (
            True  # Group similar cards together
        )
        hosted_checkout_input.card_payment_method_specific_input = (
            cardPaymentMethodSpecificInputForHostedCheckout
        )

        # Add product filtering if configured
        if (
            self.provider_id.cawl_use_product_filter
            and self.provider_id.cawl_allowed_product_ids
        ):
            allowed_product_ids = [
                product.product_id
                for product in self.provider_id.cawl_allowed_product_ids
                if product.is_active
            ]
            if allowed_product_ids:
                paymentProductFiltersHostedCheckout = (
                    PaymentProductFiltersHostedCheckout()
                )
                paymentProductFilter = PaymentProductFilter()
                paymentProductFilter.products = allowed_product_ids
                paymentProductFiltersHostedCheckout.restrict_to = paymentProductFilter
                hosted_checkout_input.payment_product_filters = (
                    paymentProductFiltersHostedCheckout
                )
                _logger.info(
                    "CAWL hosted checkout configured with %d allowed products",
                    len(allowed_product_ids),
                )

        # Prepare checkout request
        checkout_request = CreateHostedCheckoutRequest()
        checkout_request.order = order
        checkout_request.hosted_checkout_specific_input = hosted_checkout_input

        return checkout_request

    def _process_payment_status_update(self, notification_data):
        """Process payment status update notification from CAWL webhook."""
        _logger.info(
            "Processing payment status update for transaction %s: %s",
            self.reference,
            pprint.pformat(notification_data),
        )

        # Extract payment information
        payment_data = notification_data.get("payment", {})
        if not payment_data:
            _logger.warning(
                "No payment data found in notification for transaction %s",
                self.reference,
            )
            return

        # Extract payment ID and status
        payment_id = payment_data.get("id")
        payment_status = payment_data.get("status")

        if not payment_id:
            _logger.warning(
                "No payment ID found in notification for transaction %s", self.reference
            )
            return

        # Check if this webhook matches our transaction reference
        webhook_reference = None
        if "paymentOutput" in payment_data:
            payment_output = payment_data["paymentOutput"]
            if "references" in payment_output:
                references = payment_output["references"]
                webhook_reference = references.get("merchantReference")

        # Only process if this webhook is for our transaction
        if webhook_reference != self.reference:
            _logger.info(
                "Ignoring webhook for different transaction reference: %s (ours: %s)",
                webhook_reference,
                self.reference,
            )
            return

        # Update CAWL payment ID if this is a newer one (capture operations create new payment IDs)
        if payment_id != self.cawl_payment_id:
            if self.cawl_payment_id:
                _logger.info(
                    "Updating CAWL payment ID for transaction %s: %s -> %s",
                    self.reference,
                    self.cawl_payment_id,
                    payment_id,
                )
            else:
                _logger.info(
                    "Setting CAWL payment ID for transaction %s: %s",
                    self.reference,
                    payment_id,
                )
            self.cawl_payment_id = payment_id

        # Process the payment status
        if payment_status:
            self._cawl_process_payment_status(payment_status, notification_data)

        _logger.info(
            "CAWL webhook processed successfully for transaction %s", self.reference
        )

    def _process_refund_notification(self, notification_data):
        """Process refund notification from CAWL webhook."""
        _logger.info(
            "Processing refund notification for transaction %s: %s",
            self.reference,
            pprint.pformat(notification_data),
        )

        # Extract refund information
        refund_data = notification_data.get("refund", {})
        if not refund_data:
            _logger.warning(
                "No refund data found in notification for transaction %s",
                self.reference,
            )
            return

        refund_id = refund_data.get("id")
        refund_status = refund_data.get("status")
        refund_status_code = None

        # Extract status code from statusOutput
        if "statusOutput" in refund_data:
            status_output = refund_data["statusOutput"]
            refund_status_code = status_output.get("statusCode")

        _logger.info(
            "Refund %s for transaction %s: status=%s, code=%s",
            refund_id,
            self.reference,
            refund_status,
            refund_status_code,
        )

        # Find the refund transaction by merchant reference (like Stripe does)
        # The merchant reference for refunds is typically "ORIGINAL_REF_refund"
        merchant_reference = None
        if "refundOutput" in refund_data:
            refund_output = refund_data["refundOutput"]
            if "references" in refund_output:
                merchant_reference = refund_output["references"].get(
                    "merchantReference"
                )

        if not merchant_reference:
            _logger.warning(
                "No merchant reference found in refund data for transaction %s",
                self.reference,
            )
            return

        # Find the refund transaction by merchant reference
        refund_tx = self.env["payment.transaction"].search(
            [("provider_code", "=", "cawl"), ("reference", "=", merchant_reference)],
            limit=1,
        )

        if not refund_tx:
            _logger.warning(
                "No refund transaction found for merchant reference %s",
                merchant_reference,
            )
            return

        # Update refund transaction status based on CAWL status
        # Follow Odoo's pattern: immediate status update from webhook
        if refund_status == "REFUNDED" and refund_status_code == 8:
            # Refund completed successfully
            refund_tx._set_done()
            _logger.info(
                "Refund transaction %s marked as done (REFUNDED)", refund_tx.reference
            )

            # Trigger post-processing to update order/payment records (like Stripe does)
            try:
                self.env.ref("payment.cron_post_process_payment_tx")._trigger()
                _logger.info(
                    "Triggered post-processing for refund transaction %s",
                    refund_tx.reference,
                )
            except Exception as e:
                _logger.warning(
                    "Failed to trigger post-processing for refund %s: %s",
                    refund_tx.reference,
                    str(e),
                )

        elif refund_status == "REFUND_REQUESTED" and refund_status_code == 81:
            # Refund is pending
            refund_tx._set_pending()
            _logger.info(
                "Refund transaction %s marked as pending (REFUND_REQUESTED)",
                refund_tx.reference,
            )

        elif refund_status in ["REFUSED", "DECLINED"] or refund_status_code in [83, 84]:
            # Refund was refused or declined
            refund_tx._set_error(
                f"Refund {refund_status} by CAWL (code: {refund_status_code})"
            )
            _logger.warning(
                "Refund transaction %s marked as error: %s (code: %s)",
                refund_tx.reference,
                refund_status,
                refund_status_code,
            )

        elif refund_status_code == 82:  # Uncertain refund
            # Keep in pending state but log the uncertainty
            refund_tx._set_pending()
            _logger.info(
                "Refund transaction %s marked as pending (UNCERTAIN_REFUND)",
                refund_tx.reference,
            )

        else:
            _logger.info(
                "Refund transaction %s status unchanged: %s (code: %s)",
                refund_tx.reference,
                refund_status,
                refund_status_code,
            )

    def _cawl_prepare_customer_data(self):
        """Prepare customer data for CAWL API."""
        partner = self.partner_id

        # Prepare personal name
        personal_name = PersonalName()

        # Handle partner name - res.partner doesn't have firstname/lastname by default
        if partner.name:
            name_parts = partner.name.strip().split()
            if len(name_parts) >= 2:
                personal_name.first_name = name_parts[0]
                personal_name.surname = " ".join(
                    name_parts[1:]
                )  # Join remaining parts as surname
            elif len(name_parts) == 1:
                personal_name.first_name = name_parts[0]
                personal_name.surname = "Customer"  # Default surname
            else:
                personal_name.first_name = "Customer"
                personal_name.surname = "User"
        else:
            # Fallback if no name is provided
            personal_name.first_name = "Customer"
            personal_name.surname = "User"

        # Prepare contact details
        contact_details = ContactDetails()
        if partner.email:
            contact_details.email_address = partner.email
        if partner.phone:
            contact_details.phone_number = partner.phone

        # Prepare billing address
        billing_address = None
        if partner.street or partner.city:
            billing_address = Address()
            billing_address.street = partner.street or ""
            billing_address.city = partner.city or ""
            billing_address.zip = partner.zip or ""
            billing_address.country_code = (
                partner.country_id.code if partner.country_id else "FR"
            )

        # Prepare customer
        customer = Customer()
        customer.personal_information = personal_name
        customer.contact_details = contact_details
        if billing_address:
            customer.billing_address = billing_address

        return customer

    def _get_cawl_return_url(self):
        """Get the return URL for CAWL hosted checkout."""
        base_url = self.provider_id.get_base_url()
        return urls.url_join(base_url, f"/payment/cawl/return/{self.id}")

    def _process_notification_data(self, notification_data):
        """Process CAWL webhook notification data."""

        super()._process_notification_data(notification_data)
        if self.provider_code != "cawl":
            return

        # Extract webhook type
        webhook_type = notification_data.get("type")
        if not webhook_type:
            _logger.warning(
                "No webhook type found in notification data for transaction %s",
                self.reference,
            )
            return

        # Check if we've already processed this webhook (prevent duplicates)
        webhook_id = notification_data.get("id")
        if webhook_id:
            # Check if we've already processed this webhook ID using a more robust method
            # Since we can't rely on in-memory tracking across requests, we'll use a simple approach:
            # Only process webhooks if the transaction state hasn't changed recently
            # This prevents duplicate processing of the same webhook type
            if self.state in ["done", "error"] and webhook_type in [
                "payment.created",
                "payment.pending_capture",
            ]:
                _logger.info(
                    "Skipping webhook %s for transaction %s: transaction already in final state %s",
                    webhook_id,
                    self.reference,
                    self.state,
                )
                return

            # For status update webhooks, use a simple heuristic to prevent duplicates:
            # If we're processing the same webhook type and the transaction state hasn't changed,
            # it's likely a duplicate
            if webhook_type in [
                "payment.pending_capture",
                "payment.capture_requested",
                "payment.captured",
            ]:
                # These webhooks should only be processed once per transaction
                # If the transaction is already in a state that indicates these were processed, skip
                if self.state in ["done", "error"]:
                    _logger.info(
                        "Skipping webhook %s for transaction %s: transaction already in final state %s",
                        webhook_id,
                        self.reference,
                        self.state,
                    )
                    return

        # First, check if this webhook is meant for our transaction
        # Extract merchant reference from the webhook data
        merchant_reference = None

        # Handle payment webhooks
        if "payment" in notification_data:
            payment_data = notification_data["payment"]
            if "paymentOutput" in payment_data:
                payment_output = payment_data["paymentOutput"]
                if "references" in payment_output:
                    merchant_reference = payment_output["references"].get(
                        "merchantReference"
                    )

        # Handle refund webhooks
        elif "refund" in notification_data:
            refund_data = notification_data["refund"]
            if "refundOutput" in refund_data:
                refund_output = refund_data["refundOutput"]
                if "references" in refund_output:
                    merchant_reference = refund_output["references"].get(
                        "merchantReference"
                    )

        # If we can't find a merchant reference or it doesn't match our transaction, ignore this webhook
        if not merchant_reference or merchant_reference != self.reference:
            _logger.info(
                "Ignoring webhook for transaction %s: merchant reference '%s' doesn't match",
                self.reference,
                merchant_reference,
            )
            return

        # Payment events we care about
        if webhook_type in [
            "payment.created",  # Initial payment creation
            "payment.redirected",  # Consumer redirected for authentication
            "payment.authorization_requested",  # Authorization requested
            "payment.pending_approval",  # Waiting for approval
            "payment.pending_completion",  # Waiting for completion
            "payment.pending_capture",  # Waiting for capture
            "payment.capture_requested",  # Capture requested
            "payment.captured",  # Payment captured
            "payment.rejected",  # Payment rejected
            "payment.rejected_capture",  # Capture rejected
            "payment.cancelled",  # Payment cancelled
        ]:
            _logger.info(
                "Processing payment event for transaction %s: %s",
                self.reference,
                webhook_type,
            )
            try:
                self._process_payment_status_update(notification_data)
            except Exception as e:
                _logger.error(
                    "Error processing payment webhook %s for transaction %s: %s",
                    webhook_type,
                    self.reference,
                    str(e),
                )
                # Don't re-raise - we want to return 200 to CAWL even if processing fails
            return

        # Refund events we care about
        elif webhook_type in [
            "payment.refunded",  # Payment refunded
            "refund.refund_requested",  # Refund requested
        ]:
            _logger.info(
                "Processing refund event for transaction %s: %s",
                self.reference,
                webhook_type,
            )
            try:
                self._process_refund_notification(notification_data)
            except Exception as e:
                _logger.error(
                    "Error processing refund webhook %s for transaction %s: %s",
                    webhook_type,
                    self.reference,
                    str(e),
                )
                # Don't re-raise - we want to return 200 to CAWL even if processing fails
            return

        # Payment link events (ignore for now)
        elif webhook_type.startswith("paymentlink."):
            _logger.info(
                "Ignoring payment link event for transaction %s: %s",
                self.reference,
                webhook_type,
            )
            return

        # Unknown event types - log and ignore
        else:
            _logger.info(
                "Ignoring unknown webhook event for transaction %s: %s",
                self.reference,
                webhook_type,
            )
            return

    def _cawl_process_payment_status(self, status, notification_data):
        """Process CAWL payment status and update transaction state."""
        _logger.info(
            "Processing CAWL status '%s' for transaction %s (current state: %s)",
            status,
            self.reference,
            self.state,
        )

        # Define status hierarchy (higher numbers = more advanced states)
        status_hierarchy = {
            "CREATED": 0,
            "PENDING_PAYMENT": 1,
            "PENDING_COMPLETION": 2,
            "AUTHORIZATION_REQUESTED": 3,
            "PENDING_CAPTURE": 5,
            "CAPTURE_REQUESTED": 6,
            "CAPTURED": 7,
            "PAID": 8,
            "CANCELLED": -1,
            "CANCELLED_BY_CONSUMER": -1,
            "REJECTED": -2,
            "REJECTED_CAPTURE": -2,
        }

        # Get current status level
        current_level = status_hierarchy.get(self.state, 0)
        new_level = status_hierarchy.get(status, 0)

        _logger.info(
            "Status transition: %s (level %s) -> %s (level %s)",
            self.state,
            current_level,
            status,
            new_level,
        )

        # Prevent downgrading transaction state (except for cancellations/rejections)
        if new_level < current_level and new_level >= 0:
            _logger.warning(
                "Ignoring webhook status downgrade: %s -> %s for transaction %s",
                self.state,
                status,
                self.reference,
            )
            return

        # Map CAWL status values to transaction states
        if status in ["CAPTURED", "PAID"]:
            # Payment successful and captured - set to done
            if self.state != "done":
                # Don't update payment ID - keep the original one
                # The webhook 'id' field is not the payment ID
                self._set_done()
                _logger.info(
                    "Transaction %s set to done (status: %s)", self.reference, status
                )
            else:
                _logger.info(
                    "Transaction %s already done, ignoring status: %s",
                    self.reference,
                    status,
                )
            # Odoo's core payment system automatically handles sales order confirmation

        elif status == "PENDING_CAPTURE":
            # Payment authorized but not captured
            if self.state not in ["done", "error"]:
                # Check if manual capture is enabled
                if self.provider_id.capture_manually:
                    # For manual capture, set to 'authorized' state instead of 'pending'
                    self._set_authorized()
                    _logger.info(
                        "Transaction %s set to authorized (PENDING_CAPTURE - manual capture enabled)",
                        self.reference,
                    )
                else:
                    # For automatic capture, set to pending and try to capture
                    self._set_pending()
                    _logger.info(
                        "Transaction %s set to pending (PENDING_CAPTURE - attempting automatic capture)",
                        self.reference,
                    )

                    try:
                        self._cawl_capture_payment()
                        _logger.info(
                            "Automatic capture successful for payment %s",
                            self.reference,
                        )
                    except Exception as e:
                        _logger.error(
                            "Automatic capture failed for payment %s: %s",
                            self.reference,
                            str(e),
                        )
                        # Keep in pending state - user can manually capture
                        _logger.info(
                            "Payment %s remains in pending state - manual capture may be required",
                            self.reference,
                        )
            else:
                _logger.info(
                    "Transaction %s already in final state %s, ignoring PENDING_CAPTURE",
                    self.reference,
                    self.state,
                )

        elif status in ["PENDING_PAYMENT", "PENDING_COMPLETION", "CREATED"]:
            # Payment is pending - only set pending if not already done
            if self.state not in ["done", "error"]:
                self._set_pending()
                _logger.info(
                    "Transaction %s set to pending (status: %s)", self.reference, status
                )
            else:
                _logger.info(
                    "Transaction %s already in final state %s, ignoring status: %s",
                    self.reference,
                    self.state,
                    status,
                )

        elif status in ["CANCELLED", "CANCELLED_BY_CONSUMER"]:
            # Payment cancelled - can always cancel
            self._set_canceled()
            _logger.info(
                "Transaction %s cancelled (status: %s)", self.reference, status
            )

        elif status in ["REJECTED", "REJECTED_CAPTURE", "AUTHORIZATION_REQUESTED"]:
            # Payment failed/rejected - can always set error
            self._set_error("Payment was rejected by the payment provider")
            _logger.info(
                "Transaction %s set to error (status: %s)", self.reference, status
            )

        else:
            # Unknown status
            _logger.warning(
                "Unknown CAWL payment status '%s' for transaction %s",
                status,
                self.reference,
            )
            # Don't change state for unknown statuses

    def _cawl_verify_webhook_signature(self, payload, signature, webhook_key):
        """Verify CAWL webhook signature for security."""
        import hashlib
        import hmac

        # Calculate expected signature
        expected_signature = hmac.new(
            webhook_key.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256
        ).hexdigest()

        # Compare signatures (constant time comparison)
        return hmac.compare_digest(signature, expected_signature)

    def _get_tx_from_notification_data(self, provider_code, notification_data):
        """Override to find transaction from CAWL notification data."""
        tx = super()._get_tx_from_notification_data(provider_code, notification_data)

        if provider_code != "cawl" or tx:
            return tx

        # Try to find transaction by CAWL checkout ID
        checkout_id = notification_data.get("hostedCheckoutId")
        if checkout_id:
            tx = self.search([("cawl_checkout_id", "=", checkout_id)], limit=1)

        # Try to find by merchant reference
        if not tx:
            merchant_ref = notification_data.get("merchantReference")
            if merchant_ref:
                tx = self.search([("reference", "=", merchant_ref)], limit=1)

        return tx

    def _get_user_friendly_error_message(self, error_string):
        """Convert technical error messages to user-friendly ones."""
        error_lower = error_string.lower()

        # Common CAWL API error patterns
        if "sdk not available" in error_lower or "import" in error_lower:
            return _(
                "Payment service is temporarily unavailable. Please try again later or contact support."
            )
        elif (
            "authentication" in error_lower
            or "unauthorized" in error_lower
            or "api key" in error_lower
        ):
            return _("Payment service configuration error. Please contact support.")
        elif (
            "network" in error_lower
            or "connection" in error_lower
            or "timeout" in error_lower
        ):
            return _(
                "Unable to connect to payment service. Please check your internet connection and try again."
            )
        elif "currency" in error_lower and (
            "invalid" in error_lower or "not supported" in error_lower
        ):
            return _("This currency is not supported for CAWL payments.")
        elif "amount" in error_lower and (
            "invalid" in error_lower or "minimum" in error_lower
        ):
            return _(
                "Invalid payment amount. Please check the order total and try again."
            )
        elif "merchant" in error_lower and (
            "invalid" in error_lower or "not found" in error_lower
        ):
            return _("Payment service configuration error. Please contact support.")
        elif "customer" in error_lower or "contact" in error_lower:
            return _(
                "Customer information is incomplete. Please verify your details and try again."
            )
        else:
            # Generic fallback for unknown errors
            return _(
                "Unable to create payment session. Please try again or contact support."
            )

    def _cawl_log_transaction_state(self, message, level="info"):
        """Log transaction state changes for debugging."""
        log_message = f"CAWL Transaction {self.reference}: {message}"
        if level == "error":
            _logger.error(log_message)
        elif level == "warning":
            _logger.warning(log_message)
        else:
            _logger.info(log_message)

    def _send_capture_request(self):
        """Override of payment to send a capture request to CAWL.

        Note: self.ensure_one()

        :return: None
        """
        super()._send_capture_request()
        if self.provider_code != "cawl":
            return

        # Make the capture request to CAWL
        try:
            self._cawl_capture_payment()
            _logger.info(
                "Capture request successful for transaction with reference %s",
                self.reference,
            )
        except Exception as e:
            _logger.error(
                "Capture request failed for transaction with reference %s: %s",
                self.reference,
                str(e),
            )
            # Set error state on the transaction
            self._set_error(str(e))

    def _cawl_capture_payment(self):
        """Capture a payment that is in PENDING_CAPTURE state."""
        self.ensure_one()

        if not CAWL_SDK_AVAILABLE:
            raise UserError(_("CAWL SDK not available for payment capture"))

        if not self.cawl_payment_id:
            raise UserError(_("No CAWL payment ID found for capture"))

        if self.state != "pending":
            _logger.warning(
                "Cannot capture payment %s in state %s", self.reference, self.state
            )
            return

        provider = self.provider_id

        # Initialize CAWL client
        client = self._get_cawl_client()

        try:
            # Create capture request
            from onlinepayments.sdk.domain.capture_payment_request import (
                CapturePaymentRequest,
            )

            capture_request = CapturePaymentRequest()

            # Set the amount to capture (full amount)
            from onlinepayments.sdk.domain.amount_of_money import AmountOfMoney

            amount_of_money = AmountOfMoney()
            amount_of_money.amount = int(
                float_round(self.amount * 100, precision_digits=0)
            )  # Convert to cents
            amount_of_money.currency_code = self.currency_id.name
            capture_request.amount_of_money = amount_of_money

            # Capture the payment
            response = (
                client.merchant(provider.cawl_pspid)
                .payments()
                .capture_payment(self.cawl_payment_id, capture_request)
            )

            _logger.info(
                "CAWL payment capture successful for %s: %s",
                self.reference,
                response.id,
            )

            # Don't update the payment ID - keep the original one
            # The capture response ID is not the payment ID

            # The capture will trigger a webhook with updated status
            # We don't need to manually update the transaction state here

        except Exception as e:
            _logger.error(
                "CAWL payment capture failed for %s: %s", self.reference, str(e)
            )

            # Map CAWL API errors to user-friendly messages
            if "authentication" in str(e).lower() or "unauthorized" in str(e).lower():
                raise UserError(
                    _("Payment service configuration error. Please contact support.")
                )
            elif "not_found" in str(e).lower() or "404" in str(e).lower():
                raise UserError(_("Payment not found. Cannot capture."))
            elif "already_captured" in str(e).lower():
                _logger.info("Payment %s already captured", self.reference)
                return  # This is not an error
            elif "amount" in str(e).lower():
                raise UserError(
                    _("Invalid capture amount. Please check the amount and try again.")
                )
            else:
                raise UserError(_("Payment capture error: %s") % str(e))

    def _send_refund_request(self, amount_to_refund=None):
        """Override of payment to send a refund request to CAWL.

        Note: self.ensure_one()

        :param float amount_to_refund: The amount to refund.
        :return: The refund transaction created to process the refund request.
        :rtype: recordset of `payment.transaction`
        """
        refund_tx = super()._send_refund_request(amount_to_refund=amount_to_refund)
        if self.provider_code != "cawl":
            return refund_tx

        # Make the refund request to CAWL
        try:
            # Check if the transaction is eligible for refunds
            is_eligible, reason = self._cawl_check_refund_eligibility()
            if not is_eligible:
                raise UserError(_("Refund not allowed: %s") % reason)

            refund_response = self._cawl_create_refund(
                amount_to_refund, refund_tx.reference
            )

            # Store the refund ID in the refund transaction's provider_reference
            refund_tx.provider_reference = refund_response.id

            _logger.info(
                "CAWL refund request successful for transaction %s: %s",
                self.reference,
                refund_response.id,
            )

        except Exception as e:
            _logger.error(
                "CAWL refund request failed for transaction %s: %s",
                self.reference,
                str(e),
            )
            # Set error state on the refund transaction
            refund_tx._set_error(str(e))

        return refund_tx

    def _cawl_check_refund_eligibility(self):
        """Check if the transaction is eligible for refunds."""
        self.ensure_one()

        if not CAWL_SDK_AVAILABLE:
            return False, "CAWL SDK not available"

        if not self.cawl_payment_id:
            return False, "No CAWL payment ID found"

        if self.state != "done":
            return False, f"Transaction not in 'done' state (current: {self.state})"

        # Simple check: if transaction is in 'done' state, it's ready for refunds
        # This handles all cases including webhook failures and status mismatches
        _logger.info(
            "Transaction %s is in 'done' state, allowing refunds", self.reference
        )
        return True, "Payment is captured and ready for refunds"

    def _cawl_create_refund(self, amount_to_refund, refund_reference):
        """Create a refund through CAWL API using the SDK."""
        self.ensure_one()

        if not CAWL_SDK_AVAILABLE:
            _logger.error("CAWL SDK not available when creating refund")
            raise UserError(_("CAWL SDK not available. Please install dependencies."))

        if not self.cawl_payment_id:
            raise UserError(_("No CAWL payment ID found for refund"))

        provider = self.provider_id

        # Initialize CAWL client
        client = self._get_cawl_client()

        # Prepare refund request with the refund transaction reference
        refund_request = self._cawl_prepare_refund_request(
            amount_to_refund, refund_reference
        )

        try:
            # Create refund through CAWL API
            response = (
                client.merchant(provider.cawl_pspid)
                .payments()
                .refund_payment(self.cawl_payment_id, refund_request)
            )

            _logger.info("CAWL refund created successfully: %s", response.id)
            return response

        except Exception as e:
            _logger.error(
                "CAWL API error during refund creation for transaction %s: %s",
                self.reference,
                str(e),
            )

            # Log additional details for debugging
            _logger.error(
                "Transaction details - ID: %s, State: %s, Operation: %s, CAWL Payment ID: %s",
                self.id,
                self.state,
                self.operation,
                self.cawl_payment_id,
            )

            # Check if we can get payment details to understand the current state
            try:
                payment_details = (
                    client.merchant(provider.cawl_pspid)
                    .payments()
                    .get_payment(self.cawl_payment_id)
                )
                _logger.error(
                    "CAWL Payment details - Status: %s, Status Code: %s",
                    getattr(payment_details, "status", "Unknown"),
                    getattr(payment_details, "status_code", "Unknown"),
                )
            except Exception as detail_error:
                _logger.error(
                    "Could not retrieve payment details: %s", str(detail_error)
                )

            # Map CAWL API errors to user-friendly messages
            if "authentication" in str(e).lower() or "unauthorized" in str(e).lower():
                raise UserError(
                    _("Payment service configuration error. Please contact support.")
                )
            elif "network" in str(e).lower() or "connection" in str(e).lower():
                raise UserError(
                    _(
                        "Unable to connect to payment service. Please check your internet connection and try again."
                    )
                )
            elif "amount" in str(e).lower():
                raise UserError(
                    _("Invalid refund amount. Please check the amount and try again.")
                )
            elif "ACTION_NOT_ALLOWED_ON_TRANSACTION" in str(e):
                raise UserError(
                    _(
                        "Refund not allowed on this transaction. The payment may not be settled yet or refunds may not be supported for this payment method. Please contact support."
                    )
                )
            else:
                raise UserError(_("Payment gateway error: %s") % str(e))

    def _cawl_prepare_refund_request(self, amount_to_refund, refund_reference):
        """Prepare the CAWL refund request."""
        self.ensure_one()

        # Convert amount to cents (CAWL expects integer amounts)
        amount_cents = int(float_round(amount_to_refund * 100, precision_digits=0))

        # Prepare refund references
        refund_references = PaymentReferences()
        refund_references.merchant_reference = refund_reference

        # Prepare amount of money
        amount_of_money = AmountOfMoney()
        amount_of_money.amount = amount_cents
        amount_of_money.currency_code = self.currency_id.name

        # Prepare refund request
        refund_request = RefundRequest()
        refund_request.amount_of_money = amount_of_money
        refund_request.references = refund_references

        return refund_request
